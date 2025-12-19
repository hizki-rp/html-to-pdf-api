import os
import tempfile
import shutil
import subprocess
from urllib.parse import urljoin

from django.http import JsonResponse, FileResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt


def _find_chromium_exe():
    candidates = [
        r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@csrf_exempt
def convert_html(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    browser = _find_chromium_exe()
    if not browser:
        return JsonResponse({"error": "Chromium-based browser not found on server"}, status=500)

    html_file = request.FILES.get("file")
    html_url = request.POST.get("url")

    if not html_file and not html_url and not request.body:
        return HttpResponseBadRequest("Provide 'file' or 'url' or raw HTML body")

    tmpdir = tempfile.mkdtemp(prefix="html2pdf_")
    pdf_path = os.path.join(tmpdir, "output.pdf")

    try:
        if html_file:
            html_path = os.path.join(tmpdir, html_file.name)
            with open(html_path, "wb") as f:
                for chunk in html_file.chunks():
                    f.write(chunk)
            target = f"file:///{html_path.replace(os.sep, '/') }"
        elif html_url:
            target = html_url
        else:
            ct = request.headers.get("Content-Type", "")
            if "text/html" not in ct:
                return HttpResponseBadRequest("Raw body must be text/html")
            html_path = os.path.join(tmpdir, "index.html")
            with open(html_path, "wb") as f:
                f.write(request.body)
            target = f"file:///{html_path.replace(os.sep, '/') }"

        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={pdf_path}",
            "--print-to-pdf-no-header",
            target,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0 or not os.path.exists(pdf_path):
            return JsonResponse({
                "error": "Conversion failed",
                "stderr": result.stderr.decode("utf-8", errors="ignore"),
            }, status=500)

        filename = (html_file.name if html_file else "converted").rsplit(".", 1)[0] + ".pdf"
        resp = FileResponse(open(pdf_path, "rb"), as_attachment=True, filename=filename)
        return resp
    finally:
        def _cleanup(path):
            try:
                shutil.rmtree(path)
            except Exception:
                pass
        request_finished = getattr(request, "_finished", False)
        if request_finished:
            _cleanup(tmpdir)
        else:
            _cleanup(tmpdir)
