"""The hosted Word add-in's manifests (S3), checked offline.

Microsoft's XML validator is a web service (office-addin-manifest validate
posts the file to it), so CI cannot depend on it. These checks cover what
breaks sideloading in practice: well-formedness, the required elements in
schema order, an Id distinct from the local add-in's (so both install),
HTTPS everywhere on the one Vercel origin, the taskpane at /word, and every
icon actually present in the web app's public folder.
"""

import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
ADDIN = ROOT / "apps" / "word-addin"
PUBLIC = ROOT / "apps" / "web" / "public"
ORIGIN = "https://researchly-chi.vercel.app"
NS = {"o": "http://schemas.microsoft.com/office/appforoffice/1.1",
      "ov": "http://schemas.microsoft.com/office/taskpaneappversionoverrides",
      "bt": "http://schemas.microsoft.com/office/officeappbasictypes/1.0"}

# OfficeApp's children must appear in this order (the 1.1 schema's sequence).
ORDER = ["Id", "Version", "ProviderName", "DefaultLocale", "DisplayName",
         "Description", "IconUrl", "HighResolutionIconUrl", "SupportUrl",
         "AppDomains", "Hosts", "Requirements", "DefaultSettings",
         "Permissions", "VersionOverrides"]


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _hosted():
    return ET.parse(ADDIN / "manifest.hosted.xml").getroot()


def _served(url: str) -> Path:
    """The file in apps/web/public that a URL on the Vercel origin serves."""
    u = urlparse(url)
    assert f"{u.scheme}://{u.netloc}" == ORIGIN, url
    return PUBLIC / u.path.lstrip("/")


def test_xml_is_well_formed_with_required_elements_in_order():
    root = _hosted()
    assert _local(root.tag) == "OfficeApp"
    assert root.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "TaskPaneApp"
    present = [_local(c.tag) for c in root]
    assert present == [t for t in ORDER if t in present]
    for required in ORDER[:-1]:
        if required in ("HighResolutionIconUrl", "SupportUrl", "AppDomains",
                        "Requirements"):
            continue
        assert required in present, required
    assert re.fullmatch(r"\d+(\.\d+){0,3}", root.find("o:Version", NS).text)
    assert root.find("o:Permissions", NS).text == "ReadWriteDocument"
    assert root.find("o:Hosts/o:Host", NS).get("Name") == "Document"


def test_a_new_id_so_both_add_ins_can_be_installed():
    hosted = _hosted().find("o:Id", NS).text
    local = ET.parse(ADDIN / "manifest.xml").getroot().find("o:Id", NS).text
    assert str(uuid.UUID(hosted)) == hosted
    assert hosted != local
    assert json.loads((ADDIN / "manifest.json").read_text())["id"] not in (hosted, local)


def test_taskpane_is_the_hosted_word_route_over_https():
    root = _hosted()
    src = root.find("o:DefaultSettings/o:SourceLocation", NS).get("DefaultValue")
    assert src == f"{ORIGIN}/word"
    assert [d.text for d in root.findall("o:AppDomains/o:AppDomain", NS)] == [ORIGIN]
    urls = {u.get("id"): u.get("DefaultValue")
            for u in root.iter(f"{{{NS['bt']}}}Url")}
    assert urls["Researchly.Taskpane.Url"] == f"{ORIGIN}/word"


def test_every_url_is_https_on_the_one_origin_and_every_icon_exists():
    text = (ADDIN / "manifest.hosted.xml").read_text()
    urls = [a or b for a, b in re.findall(
        r'DefaultValue="(https?://[^"]+)"|>\s*(https?://[^<\s]+)\s*<', text)]
    assert len(urls) >= 9, urls
    for url in urls:
        assert url.startswith(ORIGIN), url
    root = _hosted()
    icons = [root.find("o:IconUrl", NS).get("DefaultValue"),
             root.find("o:HighResolutionIconUrl", NS).get("DefaultValue")]
    icons += [i.get("DefaultValue") for i in root.iter(f"{{{NS['bt']}}}Image")
              if i.get("DefaultValue")]
    for url in icons:
        assert _served(url).is_file(), url


def test_every_resid_is_defined():
    root = _hosted()
    defined = {e.get("id") for e in root.iter() if e.get("id")}
    used = {e.get("resid") for e in root.iter() if e.get("resid")}
    assert used and used <= defined, used - defined


def test_json_manifest_points_at_the_same_taskpane_and_icons():
    m = json.loads((ADDIN / "manifest.json").read_text())
    assert m["validDomains"] == [urlparse(ORIGIN).netloc]
    ext = m["extensions"][0]
    assert ext["runtimes"][0]["code"]["page"] == f"{ORIGIN}/word"
    action_ids = {a["id"] for r in ext["runtimes"] for a in r["actions"]}
    for tab in ext["ribbons"][0]["tabs"]:
        for group in tab["groups"]:
            for icon in group["icons"]:
                assert _served(icon["url"]).is_file()
            for control in group["controls"]:
                assert control["actionId"] in action_ids
                for icon in control["icons"]:
                    assert _served(icon["url"]).is_file()
    # App-level icons are files in the app package, next to the manifest.
    for rel in m["icons"].values():
        assert (ADDIN / rel).is_file(), rel


def test_local_and_hosted_add_ins_have_different_names():
    """Both can be installed at once; with the same name the owner could not
    tell which one they were opening (the local one needs server.py)."""
    import re
    here = Path(__file__).resolve().parents[3] / "apps" / "word-addin"
    names = [re.search(r'<DisplayName DefaultValue="([^"]+)"',
                       (here / f).read_text(encoding="utf-8")).group(1)
             for f in ("manifest.xml", "manifest.hosted.xml")]
    assert names[0] != names[1]
