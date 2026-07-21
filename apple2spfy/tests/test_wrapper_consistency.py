import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO_ROOT, "scripts", "auto_sync_on_drive.sh.template")
DEPLOYED = os.path.join(REPO_ROOT, "auto_sync_on_drive.sh")


def test_deployed_wrapper_is_the_template_with_only_its_placeholders_substituted():
    """The deployed auto_sync_on_drive.sh must be derivable from the template
    by substituting DRIVE_NAME and FALLBACK_PYTHON only — any other diff means
    the deployed wrapper drifted from its source of truth and needs regenerating
    via setup_drive_sync.sh."""
    template = open(TEMPLATE, encoding="utf-8").read()
    deployed = open(DEPLOYED, encoding="utf-8").read()

    drive_name_match = re.search(r'^DRIVE_NAME="([^"]+)"', deployed, re.MULTILINE)
    fallback_python_match = re.search(r'^FALLBACK_PYTHON="([^"]+)"', deployed, re.MULTILINE)
    assert drive_name_match and fallback_python_match

    rebuilt = template.replace('DRIVE_NAME="YOUR_DRIVE_NAME"', f'DRIVE_NAME="{drive_name_match.group(1)}"')
    rebuilt = rebuilt.replace("FALLBACK_PYTHON_PLACEHOLDER", fallback_python_match.group(1))

    assert rebuilt == deployed
