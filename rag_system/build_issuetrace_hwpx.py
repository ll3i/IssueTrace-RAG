import copy
import pathlib
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone


BASE_DIR = pathlib.Path(__file__).resolve().parent
VISUAL_DIR = BASE_DIR / "proposal_visuals"
SOURCE_MD = next(BASE_DIR.glob("IssueTrace_RAG_*10page.md"))
TARGET_PATH = next(p for p in BASE_DIR.glob("IssueTrace_RAG_*v2.hwpx") if p.suffix == ".hwpx")
TEMP_PATH = TARGET_PATH.with_suffix(".tmp.hwpx")
PICTURE_TEMPLATE_PATH = sorted((BASE_DIR.parent.parent / "sejong").glob("*.hwpx"))[0]

TITLE_TEXT = "IssueTrace RAG 기획서"
SUBTITLE_TEXT = "공정거래 의결서 하이브리드 검색·생성 시스템"
PREVIEW_DATE = "2026. 04. 20."
DISPLAY_WIDTH = 38000

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
}
OPF_CONTENT_NS = "http://www.idpf.org/2007/opf/"

ET.register_namespace("hp", NS["hp"])
ET.register_namespace("opf", OPF_CONTENT_NS)

IMAGE_SEQUENCE = [
    ("proposal_visuals/01_cases_by_year.png", "공개 연도별 의결서 건수"),
    ("proposal_visuals/02_violation_type_top10.png", "주요 위반유형 Top 10"),
    ("proposal_visuals/03_action_type_distribution.png", "주요 조치유형 분포"),
    ("proposal_visuals/04_chunk_composition.png", "전체 청크 구성 비중"),
    ("proposal_visuals/05_chunk_count_distribution.png", "사건별 청크 수 분포"),
    ("proposal_visuals/06_top10_longest_cases.png", "청크 수 기준 상위 10개 사건"),
]
IMAGE_LABELS = dict(IMAGE_SEQUENCE)
BIN_ITEM_IDS = {path: f"image{idx}" for idx, (path, _) in enumerate(IMAGE_SEQUENCE, start=1)}


def png_size(image_path: pathlib.Path) -> tuple[int, int]:
    with image_path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Unsupported PNG file: {image_path}")
        chunk_length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        if chunk_type != b"IHDR" or chunk_length < 8:
            raise ValueError(f"Invalid PNG header: {image_path}")
        width, height = struct.unpack(">II", handle.read(8))
        return width, height


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join("".join(t.itertext()) for t in paragraph.findall(".//hp:t", NS)).strip()


def clear_run_text(paragraph: ET.Element, text: str) -> None:
    preserved_children = []
    char_pr = "0"

    for run in paragraph.findall("hp:run", NS):
        char_pr = run.attrib.get("charPrIDRef", char_pr)
        for child in list(run):
            if child.tag.endswith("secPr") or child.tag.endswith("ctrl"):
                preserved_children.append(copy.deepcopy(child))

    for child in list(paragraph):
        paragraph.remove(child)

    run = ET.SubElement(paragraph, f"{{{NS['hp']}}}run", {"charPrIDRef": char_pr})
    for child in preserved_children:
        run.append(child)
    text_node = ET.SubElement(run, f"{{{NS['hp']}}}t")
    text_node.text = text


def clone_paragraph(template: ET.Element, text: str, next_id: int, page_break: bool = False) -> ET.Element:
    paragraph = copy.deepcopy(template)
    paragraph.attrib["id"] = str(next_id)
    paragraph.attrib["pageBreak"] = "1" if page_break else "0"
    paragraph.attrib["columnBreak"] = "0"
    paragraph.attrib["merged"] = "0"
    clear_run_text(paragraph, text)
    return paragraph


def load_picture_template() -> ET.Element:
    with zipfile.ZipFile(PICTURE_TEMPLATE_PATH, "r") as archive:
        root = ET.fromstring(archive.read("Contents/section0.xml"))
    picture = root.find(".//hp:pic", NS)
    if picture is None:
        raise RuntimeError("Picture template was not found in the reference HWPX.")
    return picture


def build_picture_paragraph(
    template: ET.Element,
    picture_template: ET.Element,
    next_id: int,
    image_rel_path: str,
    pic_id: int,
    inst_id: int,
) -> ET.Element:
    paragraph = copy.deepcopy(template)
    paragraph.attrib["id"] = str(next_id)
    paragraph.attrib["pageBreak"] = "0"
    paragraph.attrib["columnBreak"] = "0"
    paragraph.attrib["merged"] = "0"

    char_pr = "0"
    para_pr = paragraph.attrib.get("paraPrIDRef", "0")
    style_id = paragraph.attrib.get("styleIDRef", "0")
    for run in paragraph.findall("hp:run", NS):
        char_pr = run.attrib.get("charPrIDRef", char_pr)

    for child in list(paragraph):
        paragraph.remove(child)

    paragraph.attrib["paraPrIDRef"] = para_pr
    paragraph.attrib["styleIDRef"] = style_id

    run = ET.SubElement(paragraph, f"{{{NS['hp']}}}run", {"charPrIDRef": char_pr})
    picture = copy.deepcopy(picture_template)
    picture.attrib["id"] = str(pic_id)
    picture.attrib["instid"] = str(inst_id)

    image_path = BASE_DIR / image_rel_path
    width_px, height_px = png_size(image_path)
    display_height = max(1, round(DISPLAY_WIDTH * height_px / width_px))
    rect_width = max(1, round(DISPLAY_WIDTH * 12961 / 38000))
    rect_height = max(1, round(display_height * 2880 / 22800))

    org_sz = picture.find("hp:orgSz", NS)
    if org_sz is not None:
        org_sz.attrib["width"] = str(max(1, round(width_px * 1.5)))
        org_sz.attrib["height"] = str(max(1, round(height_px * 1.5)))

    cur_sz = picture.find("hp:curSz", NS)
    if cur_sz is not None:
        cur_sz.attrib["width"] = "0"
        cur_sz.attrib["height"] = "0"

    rotation = picture.find("hp:rotationInfo", NS)
    if rotation is not None:
        rotation.attrib["centerX"] = str(rect_width // 2)
        rotation.attrib["centerY"] = str(rect_height // 2)

    img_rect = picture.find("hp:imgRect", NS)
    if img_rect is not None:
        points = img_rect.findall("*")
        rect_pairs = [(0, 0), (rect_width, 0), (rect_width, rect_height), (0, rect_height)]
        for point, (x_pos, y_pos) in zip(points, rect_pairs):
            point.attrib["x"] = str(x_pos)
            point.attrib["y"] = str(y_pos)

    img_clip = picture.find("hp:imgClip", NS)
    if img_clip is not None:
        img_clip.attrib["left"] = "0"
        img_clip.attrib["top"] = "0"
        img_clip.attrib["right"] = str(width_px * 75)
        img_clip.attrib["bottom"] = str(height_px * 75)

    image_node = picture.find("hc:img", NS)
    if image_node is None:
        image_node = picture.find(".//{http://www.hancom.co.kr/hwpml/2011/core}img")
    if image_node is not None:
        image_node.attrib["binaryItemIDRef"] = BIN_ITEM_IDS[image_rel_path]

    size = picture.find("hp:sz", NS)
    if size is not None:
        size.attrib["width"] = str(DISPLAY_WIDTH)
        size.attrib["height"] = str(display_height)

    position = picture.find("hp:pos", NS)
    if position is not None:
        position.attrib["treatAsChar"] = "1"
        position.attrib["flowWithText"] = "1"
        position.attrib["vertRelTo"] = "PARA"
        position.attrib["horzRelTo"] = "PARA"
        position.attrib["vertOffset"] = "0"
        position.attrib["horzOffset"] = "0"

    shape_comment = picture.find("hp:shapeComment", NS)
    if shape_comment is not None:
        shape_comment.text = f"자동 삽입 그림\n{pathlib.Path(image_rel_path).name}"

    run.append(picture)
    ET.SubElement(run, f"{{{NS['hp']}}}t").text = ""
    return paragraph


def update_content_hpf(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    metadata = root.find(f"{{{OPF_CONTENT_NS}}}metadata")
    manifest = root.find(f"{{{OPF_CONTENT_NS}}}manifest")
    if metadata is None or manifest is None:
        return xml_bytes

    title = metadata.find(f"{{{OPF_CONTENT_NS}}}title")
    if title is not None:
        title.text = TITLE_TEXT

    now = datetime.now(timezone.utc)
    date_text = datetime.now().strftime("%Y년 %m월 %d일")

    meta_updates = {
        "creator": "Codex",
        "subject": "공정거래 의결서 하이브리드 검색·생성 시스템 기획서",
        "description": "공정거래 공개데이터 기반 IssueTrace RAG 기획서",
        "lastsaveby": "Codex",
        "ModifiedDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": date_text,
    }

    for meta in metadata.findall(f"{{{OPF_CONTENT_NS}}}meta"):
        name = meta.attrib.get("name")
        if name in meta_updates:
            meta.text = meta_updates[name]

    for item in list(manifest):
        href = item.attrib.get("href", "")
        if href.startswith("BinData/"):
            manifest.remove(item)

    for image_rel_path, _ in IMAGE_SEQUENCE:
        image_name = pathlib.Path(image_rel_path).name
        ET.SubElement(
            manifest,
            f"{{{OPF_CONTENT_NS}}}item",
            {
                "id": BIN_ITEM_IDS[image_rel_path],
                "href": f"BinData/{image_name}",
                "media-type": "image/png",
            },
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def flush_paragraph(buffer: list[str], blocks: list[tuple[str, object]]) -> None:
    if buffer:
        text = " ".join(line.strip() for line in buffer if line.strip())
        if text:
            blocks.append(("body", text))
    buffer.clear()


def parse_markdown_blocks(text: str) -> list[tuple[str, object]]:
    blocks: list[tuple[str, object]] = []
    lines = text.splitlines()
    paragraph_buffer: list[str] = []
    table_buffer: list[str] = []
    code_buffer: list[str] = []
    in_code = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(paragraph_buffer, blocks)
            if table_buffer:
                blocks.append(("table", table_buffer[:]))
                table_buffer.clear()
            if in_code:
                blocks.append(("code", code_buffer[:]))
                code_buffer.clear()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if stripped.startswith("|"):
            flush_paragraph(paragraph_buffer, blocks)
            table_buffer.append(stripped)
            continue

        if table_buffer:
            blocks.append(("table", table_buffer[:]))
            table_buffer.clear()

        if not stripped:
            flush_paragraph(paragraph_buffer, blocks)
            continue

        if stripped == "---":
            flush_paragraph(paragraph_buffer, blocks)
            continue

        if stripped.startswith("# "):
            flush_paragraph(paragraph_buffer, blocks)
            blocks.append(("title", stripped[2:].strip()))
            continue

        if stripped.startswith("## "):
            flush_paragraph(paragraph_buffer, blocks)
            blocks.append(("section", stripped[3:].strip()))
            continue

        if stripped.startswith("### "):
            flush_paragraph(paragraph_buffer, blocks)
            blocks.append(("subsection", stripped[4:].strip()))
            continue

        if stripped.startswith("![") and "](" in stripped and stripped.endswith(")"):
            flush_paragraph(paragraph_buffer, blocks)
            match = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
            if match:
                blocks.append(("image", (match.group(1).strip(), match.group(2).strip())))
            continue

        if stripped.startswith("- "):
            flush_paragraph(paragraph_buffer, blocks)
            blocks.append(("bullet", stripped[2:].strip()))
            continue

        paragraph_buffer.append(line)

    flush_paragraph(paragraph_buffer, blocks)
    if table_buffer:
        blocks.append(("table", table_buffer[:]))
    if code_buffer:
        blocks.append(("code", code_buffer[:]))
    return blocks


def table_to_rows(lines: list[str]) -> list[str]:
    rows = []
    header = None
    for idx, line in enumerate(lines):
        cols = [part.strip() for part in line.strip("|").split("|")]
        if idx == 0:
            header = cols
            continue
        if all(set(col) <= {"-"} for col in cols):
            continue
        if header and len(cols) == len(header) and len(cols) > 1:
            rows.append(" / ".join(f"{header[i]}: {cols[i]}" for i in range(len(cols))))
        else:
            rows.append(" / ".join(cols))
    return rows


def code_to_rows(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip()]


def max_numeric_attr(root: ET.Element, attr_name: str) -> int:
    max_value = 0
    for element in root.iter():
        raw = element.attrib.get(attr_name)
        if raw and raw.isdigit():
            max_value = max(max_value, int(raw))
    return max_value


def update_section(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    paragraphs = root.findall("hp:p", NS)
    if len(paragraphs) < 90:
        return xml_bytes

    title_para = paragraphs[0]
    subtitle_para = paragraphs[1]
    date_para = paragraphs[2]
    clear_run_text(title_para, TITLE_TEXT)
    clear_run_text(subtitle_para, SUBTITLE_TEXT)
    clear_run_text(date_para, PREVIEW_DATE)

    section_template = paragraphs[45]
    subsection_template = paragraphs[47]
    body_template = paragraphs[48]
    code_template = paragraphs[89]
    picture_template = load_picture_template()

    for paragraph in paragraphs[3:]:
        root.remove(paragraph)

    next_id = max_numeric_attr(root, "id") + 1
    next_pic_id = max_numeric_attr(root, "instid") + 1
    next_shape_id = max_numeric_attr(root, "id") + 1000
    blocks = parse_markdown_blocks(SOURCE_MD.read_text(encoding="utf-8"))

    first_section = True
    seen_first_section = False
    for kind, value in blocks:
        if kind == "title":
            continue

        if not seen_first_section and kind != "section":
            continue

        if kind == "section":
            seen_first_section = True
            paragraph = clone_paragraph(section_template, value, next_id, page_break=not first_section)
            first_section = False
            next_id += 1
            root.append(paragraph)
            continue

        if kind == "subsection":
            paragraph = clone_paragraph(subsection_template, value, next_id)
            next_id += 1
            root.append(paragraph)
            continue

        if kind == "body":
            paragraph = clone_paragraph(body_template, value, next_id)
            next_id += 1
            root.append(paragraph)
            continue

        if kind == "bullet":
            paragraph = clone_paragraph(body_template, f"• {value}", next_id)
            next_id += 1
            root.append(paragraph)
            continue

        if kind == "table":
            for row in table_to_rows(value):
                paragraph = clone_paragraph(body_template, row, next_id)
                next_id += 1
                root.append(paragraph)
            continue

        if kind == "code":
            for row in code_to_rows(value):
                paragraph = clone_paragraph(code_template, row, next_id)
                next_id += 1
                root.append(paragraph)
            continue

        if kind == "image":
            alt_text, image_rel_path = value
            label = IMAGE_LABELS.get(image_rel_path, alt_text or image_rel_path)
            caption = clone_paragraph(body_template, f"[시각화] {label}", next_id)
            next_id += 1
            root.append(caption)

            image_paragraph = build_picture_paragraph(
                body_template,
                picture_template,
                next_id,
                image_rel_path,
                next_shape_id,
                next_pic_id,
            )
            next_id += 1
            next_shape_id += 1
            next_pic_id += 1
            root.append(image_paragraph)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_updated_hwpx() -> None:
    preview_text = f"{TITLE_TEXT}\r\n{SUBTITLE_TEXT}\r\n{PREVIEW_DATE}\r\n"
    image_payloads = {
        pathlib.Path(image_rel_path).name: (BASE_DIR / image_rel_path).read_bytes()
        for image_rel_path, _ in IMAGE_SEQUENCE
    }

    with zipfile.ZipFile(TARGET_PATH, "r") as source, zipfile.ZipFile(TEMP_PATH, "w") as dest:
        for info in source.infolist():
            if info.filename.startswith("BinData/"):
                continue

            data = source.read(info.filename)
            if info.filename == "Contents/content.hpf":
                data = update_content_hpf(data)
            elif info.filename == "Contents/section0.xml":
                data = update_section(data)
            elif info.filename == "Preview/PrvText.txt":
                data = preview_text.encode("utf-8")
            dest.writestr(info, data)

        for image_name, payload in image_payloads.items():
            dest.writestr(f"BinData/{image_name}", payload)

    TEMP_PATH.replace(TARGET_PATH)


if __name__ == "__main__":
    write_updated_hwpx()
