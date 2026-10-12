"""Check field declarations before VTK can merge duplicate array names."""

import math
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import vtk


def validate_xml_declarations(path):
    """Inspect XML metadata, stopping before raw AppendedData payloads."""
    parser = ET.XMLPullParser(events=("start", "end"))
    stack, names = [], None

    def events():
        nonlocal names
        for event, element in parser.read_events():
            if event == "start":
                stack.append(element.tag)
                if element.tag in ("PointData", "CellData"):
                    names = set()
                elif (
                    element.tag in ("DataArray", "Array")
                    and len(stack) > 1
                    and stack[-2] in ("PointData", "CellData")
                ):
                    name = element.get("Name")
                    if not name or name in names:
                        raise ValueError(
                            f"{path.name}: invalid or duplicate field name {name!r}"
                        )
                    names.add(name)
            else:
                if element.tag in ("PointData", "CellData"):
                    names = None
                stack.pop()
                element.clear()

    try:
        with path.open("rb") as stream:
            carry = b""
            while chunk := stream.read(65536):
                chunk = carry + chunk
                index = chunk.find(b"<AppendedData")
                if index >= 0:
                    parser.feed(chunk[:index])
                    events()
                    return
                # Keep a tail so an AppendedData tag split between reads is
                # detected before any raw binary bytes reach the XML parser.
                carry = chunk[-32:]
                parser.feed(chunk[:-32])
                events()
            parser.feed(carry)
            events()
            parser.close()
    except ET.ParseError as exc:
        raise ValueError(f"{path.name}: Corrupted XML: {exc}") from exc


def validate_legacy_declarations(path):
    """Scan standard legacy headers, skipping ASCII/binary numeric payloads.

    VTK silently replaces repeated FIELD/SCALARS declarations. Validate
    names independently within PointData and CellData before that happens.
    Numeric values are still decoded by the native VTK reader.
    """
    types = {
        "bit": 0,
        "char": 1,
        "signed_char": 1,
        "unsigned_char": 1,
        "short": 2,
        "unsigned_short": 2,
        "int": 4,
        "unsigned_int": 4,
        "long": vtk.vtkLongArray().GetDataTypeSize(),
        "unsigned_long": vtk.vtkUnsignedLongArray().GetDataTypeSize(),
        "long_long": 8,
        "unsigned_long_long": 8,
        "vtktypeint64": 8,
        "vtktypeuint64": 8,
        "vtktypeint32": 4,
        "vtktypeuint32": 4,
        "float": 4,
        "double": 8,
    }
    with path.open("rb") as stream:
        stream.readline()  # Version line.
        stream.readline()  # Arbitrary title.
        binary = stream.readline().strip().upper() == b"BINARY"
        pending = b""
        section, tuples = None, 0
        names = {"POINT_DATA": set(), "CELL_DATA": set()}

        def line():
            nonlocal pending
            if pending:
                value, pending = pending, b""
                return value
            return stream.readline()

        def skip(count, dtype):
            nonlocal pending
            if count < 0:
                raise ValueError(f"{path.name}: invalid legacy array size")
            dtype = dtype.lower()
            if dtype not in types:
                raise ValueError(
                    f"{path.name}: unsupported legacy numeric type {dtype!r}"
                )
            if binary:
                size = math.ceil(count / 8) if dtype == "bit" else count * types[dtype]
                start = stream.tell()
                stream.seek(0, 2)
                end = stream.tell()
                if start + size > end:
                    raise ValueError(f"{path.name}: truncated legacy binary data")
                stream.seek(start + size)
            else:
                while count:
                    values = line().split()
                    if not values:
                        if stream.tell() == path.stat().st_size:
                            raise ValueError(
                                f"{path.name}: truncated legacy ASCII data"
                            )
                        continue
                    if len(values) > count:
                        pending = b" ".join(values[count:])
                    count -= min(count, len(values))

        def field(name):
            if section is not None:
                name = unquote(name)
                if name in names[section]:
                    raise ValueError(f"{path.name}: duplicate {section} field {name!r}")
                names[section].add(name)

        def header():
            value = line()
            while value and not value.strip():
                value = line()
            if not value:
                raise ValueError(f"{path.name}: truncated legacy header")
            return value.strip()

        def metadata(components):
            nonlocal pending
            value = line()
            while value and not value.strip():
                value = line()
            if value.strip() != b"METADATA":
                pending = value
                return
            # Metadata is always ASCII, including in binary legacy files.
            # COMPONENT_NAMES contains one physical line per component,
            # including empty names. INFORMATION ends at a blank line.
            value = line()
            while value and value.strip():
                if value.strip() == b"COMPONENT_NAMES":
                    for _ in range(components):
                        if not line():
                            raise ValueError(
                                f"{path.name}: truncated component metadata"
                            )
                elif value.startswith(b"INFORMATION "):
                    for _ in range(int(value.split()[1])):
                        key_header = header().decode().split()
                        if (
                            len(key_header) != 4
                            or key_header[0] != "NAME"
                            or key_header[2] != "LOCATION"
                        ):
                            raise ValueError(
                                f"{path.name}: invalid information metadata"
                            )
                        key = vtk.vtkInformationKeyLookup.Find(
                            key_header[1], key_header[3]
                        )
                        data_line = line().split()
                        if not data_line or data_line[0] != b"DATA":
                            raise ValueError(f"{path.name}: invalid information data")
                        if key and key.IsA("vtkInformationStringVectorKey"):
                            for _ in range(int(data_line[1])):
                                if not line():
                                    raise ValueError(
                                        f"{path.name}: truncated information vector"
                                    )
                    break
                else:
                    raise ValueError(f"{path.name}: invalid legacy METADATA")
                value = line()

        while value := line():
            tokens = value.decode("ascii", errors="replace").split()
            if not tokens:
                continue
            keyword = tokens[0].upper()
            if keyword in ("POINT_DATA", "CELL_DATA"):
                section, tuples = keyword, int(tokens[1])
            elif keyword == "POINTS":
                skip(int(tokens[1]) * 3, tokens[2])
                metadata(3)
            elif keyword in ("X_COORDINATES", "Y_COORDINATES", "Z_COORDINATES"):
                skip(int(tokens[1]), tokens[2])
                metadata(1)
            elif keyword in (
                "CELLS",
                "VERTICES",
                "LINES",
                "POLYGONS",
                "TRIANGLE_STRIPS",
            ):
                count, size = int(tokens[1]), int(tokens[2])
                following = line()
                if following.lstrip().startswith(b"OFFSETS "):
                    skip(count, following.decode().split()[1])
                    connectivity = header()
                    if not connectivity.startswith(b"CONNECTIVITY "):
                        raise ValueError(f"{path.name}: missing legacy CONNECTIVITY")
                    skip(size, connectivity.decode().split()[1])
                else:
                    pending = following
                    if binary:
                        # Put the first payload bytes back for binary v4 cells.
                        stream.seek(-len(following), 1)
                        pending = b""
                    skip(size, "int")
            elif keyword == "CELL_TYPES":
                skip(int(tokens[1]), "int")
            elif keyword == "FIELD":
                for _ in range(int(tokens[2])):
                    array_header = line().split()
                    while not array_header:
                        value = line()
                        if not value:
                            raise ValueError(
                                f"{path.name}: truncated legacy FIELD header"
                            )
                        array_header = value.split()
                    if len(array_header) != 4:
                        raise ValueError(f"{path.name}: invalid legacy FIELD header")
                    field(array_header[0].decode())
                    skip(
                        int(array_header[1]) * int(array_header[2]),
                        array_header[3].decode(),
                    )
                    metadata(int(array_header[1]))
            elif keyword == "SCALARS":
                field(tokens[1])
                lookup = header()
                if not lookup.upper().startswith(b"LOOKUP_TABLE "):
                    raise ValueError(f"{path.name}: missing scalar LOOKUP_TABLE")
                components = int(tokens[3]) if len(tokens) > 3 else 1
                skip(tuples * components, tokens[2])
                metadata(components)
            elif keyword in (
                "VECTORS",
                "NORMALS",
                "TENSORS",
                "TEXTURE_COORDINATES",
                "COLOR_SCALARS",
                "GLOBAL_IDS",
                "PEDIGREE_IDS",
            ):
                field(tokens[1])
                if keyword == "COLOR_SCALARS":
                    skip(
                        tuples * int(tokens[2]), "unsigned_char" if binary else "float"
                    )
                    metadata(int(tokens[2]))
                elif keyword == "TEXTURE_COORDINATES":
                    skip(tuples * int(tokens[2]), tokens[3])
                    metadata(int(tokens[2]))
                else:
                    components = {"VECTORS": 3, "NORMALS": 3, "TENSORS": 9}.get(
                        keyword, 1
                    )
                    skip(tuples * components, tokens[2])
                    metadata(components)
            elif keyword == "LOOKUP_TABLE" and len(tokens) > 2:
                skip(int(tokens[2]) * 4, "unsigned_char" if binary else "float")
