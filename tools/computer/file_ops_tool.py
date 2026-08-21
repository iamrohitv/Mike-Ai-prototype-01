import os
import re
import shutil

from policies.engine import Level
from tools.base import Tool


class FileOpsTool(Tool):
    name = "file_ops"
    description = "create, write, append, overwrite, delete files and folders"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "create file",
                "write to",
                "overwrite",
                "append to",
                "add to",
                "replace",
                "delete file",
                "remove file",
                "create folder",
                "make directory",
                "mkdir",
                "delete folder",
                "remove directory",
                "rmdir",
            ]
        )

    def _extract_path_and_content(self, request, trigger):
        remainder = request.lower().replace(trigger, "", 1).strip()
        if " with content " in remainder:
            path_part, content = remainder.split(" with content ", 1)
            return path_part.strip(), content.strip()
        if " " in remainder:
            path_part, content = remainder.split(" ", 1)
            return path_part.strip(), content.strip()
        return remainder, ""

    def run(self, request):
        lowered = request.lower().strip()

        if lowered.startswith("create file"):
            return self._handle_create_file(lowered)
        if lowered.startswith("write to"):
            return self._handle_write(lowered, overwrite=True, trigger="write to")
        if lowered.startswith("overwrite"):
            return self._handle_write(lowered, overwrite=True, trigger="overwrite")
        if lowered.startswith("append to"):
            return self._handle_write(lowered, overwrite=False, trigger="append to")
        if lowered.startswith("add to"):
            return self._handle_write(lowered, overwrite=False, trigger="add to")
        if " replace " in lowered or lowered.startswith("replace "):
            if " with " in lowered and " in " in lowered:
                return self._handle_replace(lowered)
        if lowered.startswith("delete file") or lowered.startswith("remove file"):
            return self._handle_delete_file(lowered)
        if lowered.startswith("create folder") or lowered.startswith("make directory") or lowered.startswith("mkdir "):
            return self._handle_create_folder(lowered)
        if lowered.startswith("delete folder") or lowered.startswith("remove directory") or lowered.startswith("rmdir "):
            return self._handle_delete_folder(lowered)

        return "I didn't understand that file operation."

    def _handle_create_file(self, request):
        path, content = self._extract_path_and_content(request, "create file")
        if not path:
            return "Which file would you like me to create?"
        level = Level.YELLOW
        self.policies.allow(f"{self.name}:create:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "create", "path": path, "content": content})
            return f"Creating {path} needs approval. Say 'approve' to proceed."
        return self._execute_create_file(path, content)

    def _handle_write(self, request, overwrite, trigger):
        path, content = self._extract_path_and_content(request, trigger)
        if not path:
            return "Which file would you like me to write?"
        if not content:
            return "What content should I write?"
        level = Level.ORANGE if overwrite else Level.YELLOW
        self.policies.allow(f"{self.name}:write:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "write", "path": path, "content": content, "overwrite": overwrite})
            return f"{'Overwriting' if overwrite else 'Appending to'} {path} needs approval. Say 'approve' to proceed."
        return self._execute_write(path, content, overwrite)

    def _handle_replace(self, request):
        match = re.search(r"replace\s+(.+?)\s+with\s+(.+?)\s+in\s+(.+)", request)
        if not match:
            return "Usage: replace <old> with <new> in <path>"
        old_text, new_text, path = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
        level = Level.ORANGE
        self.policies.allow(f"{self.name}:replace:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "replace", "path": path, "old": old_text, "new": new_text})
            return f"Replacing in {path} needs approval. Say 'approve' to proceed."
        return self._execute_replace(path, old_text, new_text)

    def _handle_delete_file(self, request):
        trigger = "delete file" if "delete file" in request else "remove file"
        path = request.replace(trigger, "", 1).strip()
        if not path:
            return "Which file would you like me to delete?"
        level = Level.ORANGE
        self.policies.allow(f"{self.name}:delete_file:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "delete_file", "path": path})
            return f"Deleting {path} needs approval. Say 'approve' to proceed."
        return self._execute_delete_file(path)

    def _handle_create_folder(self, request):
        trigger = next(t for t in ("create folder", "make directory", "mkdir ") if t in request)
        path = request.replace(trigger, "", 1).strip()
        if not path:
            return "Which folder would you like me to create?"
        level = Level.YELLOW
        self.policies.allow(f"{self.name}:create_folder:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "create_folder", "path": path})
            return f"Creating folder {path} needs approval. Say 'approve' to proceed."
        return self._execute_create_folder(path)

    def _handle_delete_folder(self, request):
        trigger = next(t for t in ("delete folder", "remove directory", "rmdir ") if t in request)
        path = request.replace(trigger, "", 1).strip()
        if not path:
            return "Which folder would you like me to delete?"
        level = Level.ORANGE
        self.policies.allow(f"{self.name}:delete_folder:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"operation": "delete_folder", "path": path})
            return f"Deleting folder {path} needs approval. Say 'approve' to proceed."
        return self._execute_delete_folder(path)

    def _execute_create_file(self, path, content):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Created {path} ({len(content)} chars)."
        except Exception as exc:
            return f"Failed to create {path}: {exc}"

    def _execute_write(self, path, content, overwrite):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            mode = "w" if overwrite else "a"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            action = "Overwrote" if overwrite else "Appended to"
            return f"{action} {path} ({len(content)} chars)."
        except Exception as exc:
            return f"Failed to write {path}: {exc}"

    def _execute_replace(self, path, old_text, new_text):
        try:
            if not os.path.isfile(path):
                return f"File not found: {path}"
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return f"Text '{old_text}' not found in {path}."
            new_content = content.replace(old_text, new_text)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            count = content.count(old_text)
            return f"Replaced {count} occurrence(s) of '{old_text}' in {path}."
        except Exception as exc:
            return f"Failed to replace in {path}: {exc}"

    def _execute_delete_file(self, path):
        try:
            if not os.path.isfile(path):
                return f"File not found: {path}"
            os.remove(path)
            return f"Deleted {path}."
        except Exception as exc:
            return f"Failed to delete {path}: {exc}"

    def _execute_create_folder(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            return f"Created folder {path}."
        except Exception as exc:
            return f"Failed to create folder {path}: {exc}"

    def _execute_delete_folder(self, path):
        try:
            if not os.path.isdir(path):
                return f"Folder not found: {path}"
            shutil.rmtree(path)
            return f"Deleted folder {path}."
        except Exception as exc:
            return f"Failed to delete folder {path}: {exc}"

    def verify(self, result):
        if "needs approval" in result or "Which" in result or "Usage:" in result:
            return "pending approval" if "needs approval" in result else "failed"
        if "Failed" in result or "not found" in result:
            return "failed"
        return "verified: file operation completed"

    def approve_pending(self, payload=None):
        payload = payload or self.policies.pending_approvals.get(self.name)
        if not payload:
            return "There is no file operation waiting for approval."
        op = payload.get("operation")
        path = payload.get("path")
        if op == "create":
            return self._execute_create_file(path, payload.get("content", ""))
        if op == "write":
            return self._execute_write(path, payload.get("content", ""), payload.get("overwrite", True))
        if op == "replace":
            return self._execute_replace(path, payload.get("old"), payload.get("new"))
        if op == "delete_file":
            return self._execute_delete_file(path)
        if op == "create_folder":
            return self._execute_create_folder(path)
        if op == "delete_folder":
            return self._execute_delete_folder(path)
        return "Unknown operation."