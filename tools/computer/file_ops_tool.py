import os
import re
import shutil

from policies.engine import Level
from tools.base import Tool
from tools.computer.locations import (
    _desktop_path, extract_location, looks_like_location_answer,
)


class FileOpsTool(Tool):
    name = "file_ops"
    description = "create, write, append, overwrite, replace, delete files and folders"
    level = Level.YELLOW

    # Regex patterns for intent classification
    CREATE_PATTERNS = [
        re.compile(r"\b(create|make|new)\s+(?:a\s+)?(?:\w+\s+)?file\b", re.I),
        re.compile(r"\b(create|make)\s+(?:a\s+)?(?:\w+\s+)?txt\s+file\b", re.I),
        re.compile(r"\b(save|write)\s+(?:this\s+)?as\s+(?:a\s+)?file\b", re.I),
    ]

    READ_PATTERNS = [
        re.compile(r"\bread\s+(?:the\s+)?file\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
        re.compile(r"\bshow\s+(?:me\s+)?(?:the\s+)?file\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
        re.compile(r"\bopen\s+(?:the\s+)?file\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
    ]

    WRITE_PATTERNS = [
        re.compile(r"\bwrite\s+to\s+\S+", re.I),
        re.compile(r"\boverwrite\s+\S+", re.I),
        re.compile(r"\bwrite\s+(?:.*?)\s+(?:to|into)\s+\S+\.(?:txt|md|py|json)", re.I),
    ]

    APPEND_PATTERNS = [
        re.compile(r"\bappend\s+.+?\s+to\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
        re.compile(r"\badd\s+to\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
        re.compile(r"\badd\s+.+?\s+(?:to|into)\s+.+?(?:\s+on\s+desktop|\s*$)", re.I),
    ]

    REPLACE_PATTERNS = [
        re.compile(r"\breplace\s+.+\s+with\s+.+\s+in\s+\S+", re.I),
    ]

    DELETE_FILE_PATTERNS = [
        re.compile(r"\bdelete\s+file\s+\S+", re.I),
        re.compile(r"\bremove\s+file\s+\S+", re.I),
        re.compile(r"\bdelete\s+\S+\.(?:txt|md|py|json)", re.I),
    ]

    CREATE_FOLDER_PATTERNS = [
        re.compile(r"\b(create|make)\s+(?:a\s+)?(?:folder|directory)\s+\S+", re.I),
        re.compile(r"\bmkdir\s+\S+", re.I),
    ]

    DELETE_FOLDER_PATTERNS = [
        re.compile(r"\b(delete|remove)\s+(?:folder|directory)\s+\S+", re.I),
        re.compile(r"\brmdir\s+\S+", re.I),
    ]

    DESKTOP_INDICATORS = [
        r"\bon\s+desktop\b",
        r"\bto\s+desktop\b",
        r"\bat\s+desktop\b",
        r"\bonto\s+desktop\b",
        r"\bdesktop\s+(?:folder|dir)\b",
    ]

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)
        self._pending_op = None

    def matches(self, request):
        if self._pending_op is not None:
            return True
        lowered = request.lower()
        for pattern in (self.CREATE_PATTERNS + self.READ_PATTERNS + self.WRITE_PATTERNS + 
                       self.APPEND_PATTERNS + self.REPLACE_PATTERNS +
                       self.DELETE_FILE_PATTERNS + self.CREATE_FOLDER_PATTERNS +
                       self.DELETE_FOLDER_PATTERNS):
            if pattern.search(lowered):
                return True
        return False

    def _get_desktop_path(self):
        """Return the real Desktop folder, checking OneDrive first."""
        candidates = [
            os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            os.path.join(os.environ.get("HOMEPATH", ""), "Desktop"),
        ]
        for p in candidates:
            if p and os.path.isdir(p):
                return p
        return os.path.join(os.path.expanduser("~"), "Desktop")

    def _classify_operation(self, text: str) -> str | None:
        lowered = text.lower()
        for pattern in self.CREATE_PATTERNS:
            if pattern.search(lowered):
                return "create"
        for pattern in self.READ_PATTERNS:
            if pattern.search(lowered):
                return "read"
        for pattern in self.WRITE_PATTERNS:
            if pattern.search(lowered):
                return "write"
        for pattern in self.APPEND_PATTERNS:
            if pattern.search(lowered):
                return "append"
        for pattern in self.REPLACE_PATTERNS:
            if pattern.search(lowered):
                return "replace"
        for pattern in self.DELETE_FILE_PATTERNS:
            if pattern.search(lowered):
                return "delete_file"
        for pattern in self.CREATE_FOLDER_PATTERNS:
            if pattern.search(lowered):
                return "create_folder"
        for pattern in self.DELETE_FOLDER_PATTERNS:
            if pattern.search(lowered):
                return "delete_folder"
        return None

    TYPE_EXT = {
        "python": "py", "py": "py", "markdown": "md", "md": "md",
        "json": "json", "csv": "csv", "html": "html", "htm": "htm",
        "javascript": "js", "js": "js", "java": "java",
        "powershell": "ps1", "ps1": "ps1", "batch": "bat", "bat": "bat",
        "yaml": "yml", "yml": "yml", "xml": "xml", "sql": "sql",
    }

    def _extract_parameters(self, text: str, operation: str) -> dict:
        lowered = text.lower()

        # 'python file', 'markdown file' etc. -> extension, not filename
        forced_ext = None
        type_match = re.search(
            r"\b(" + "|".join(self.TYPE_EXT) + r")\b"
            r"(?=\s+(?:file|files)\b)", lowered,
        )
        if type_match:
            forced_ext = self.TYPE_EXT[type_match.group(1)]

        # Detect desktop reference anywhere
        on_desktop = any(re.search(p, lowered) for p in [
            r"\bon\s+desktop\b",
            r"\bto\s+desktop\b",
            r"\bat\s+desktop\b",
            r"\bonto\s+desktop\b",
            r"\bdesktop\s+(?:folder|dir)\b",
        ])

        # Extract content (after "with content", "containing", "saying", etc.)
        content = ""
        content_match = re.search(
            r"(?:with\s+content|containing|saying|content\s+is|text\s+is)\s+(.+)",
            lowered
        )
        if content_match:
            content = content_match.group(1).strip()
            # Remove content phrase from text for path extraction
            lowered = lowered[:content_match.start()].strip()

        # Also check for "write X to Y" or "append X to Y" patterns
        if operation in ("write", "append") and not content:
            # Pattern: "write <content> to <file>" or "append <content> to <file>"
            write_match = re.search(r"(?:write|append|add)\s+(.+?)\s+to\s+(.+)", lowered)
            if write_match:
                content = write_match.group(1).strip()
                # The rest after "to" is the file path
                file_part = write_match.group(2).strip()
                lowered = file_part  # Use just the file part for path extraction

# Extract filename/path
        path = ""
        # Handle "named X as a txt file" / "named X as a file" pattern first
        named_as_match = re.search(r"\b(?:named|called)\s+([^,\.]+?)\s+as\s+a\s+(?:txt\s+)?file\b", lowered)
        if named_as_match:
            path = named_as_match.group(1).strip()
            lowered = lowered[:named_as_match.start()].strip()
        else:
            # Handle "named X" / "called X" - stop at location words
            name_match = re.search(r"\b(?:named|called)\s+([^,\.]+?)(?:\s+(?:on|to|at|in|into)\s+desktop|\s*$)", lowered)
            if name_match:
                path = name_match.group(1).strip()
                lowered = lowered[:name_match.start()].strip()
            else:
                name_match = re.search(r"\b(?:named|called)\s+([^,\.]+)", lowered)
                if name_match:
                    path = name_match.group(1).strip()
                    lowered = lowered[:name_match.start()].strip()
                else:
                    # "as X" but not "as a file"
                    as_match = re.search(r"\bas\s+([^,\.]+?)(?:\s+as\s+a\s+(?:txt\s+)?file|\s*$)", lowered)
                    if as_match:
                        path = as_match.group(1).strip()
                        lowered = lowered[:as_match.start()].strip()
                    else:
                        # Handle replace: "replace X with Y in <file>"
                        if operation == "replace":
                            replace_path_match = re.search(r"replace\s+.+?\s+with\s+.+?\s+in\s+([^,\s]+?)(?:\s+(?:on|to|at|in|into)\s+desktop|\s*$)", text, re.I)
                            if replace_path_match:
                                path = replace_path_match.group(1).strip()
                            else:
                                # Fallback to general pattern
                                replace_path_match = re.search(r"in\s+([^,\s]+?)(?:\s+(?:on|to|at|in|into)\s+desktop|\s*$)", text, re.I)
                                if replace_path_match:
                                    path = replace_path_match.group(1).strip()
                        else:
                            # Fallback: extract from remaining text
                            path_text = lowered
                            # Remove desktop references
                            path_text = re.sub(r"\s+(?:on|to|at|in|into)\s+desktop\b", "", path_text)
                            path_text = re.sub(r"\bdesktop\b", "", path_text)
                            # Remove "as a txt file" / "as a file" suffixes
                            path_text = re.sub(r"\s+as\s+a\s+(?:txt\s+)?file\b", "", path_text)
                            
                            # Remove common operation words
                            skip_words = {"create", "make", "new", "write", "append", "add",
                                          "overwrite", "replace", "delete", "remove", "file",
                                          "read", "txt", "text", "folder", "directory", "a", "an", "the",
                                          "with", "content", "containing", "saying", "called", "named", "as",
                                          "to", "into", "on", "at", "in"}
                            if forced_ext:
                                skip_words.update(self.TYPE_EXT)

                            tokens = path_text.strip().split()
                            path_tokens = [t for t in tokens if t not in skip_words]
                            if path_tokens:
                                path = " ".join(path_tokens[-4:])  # last 4 meaningful words

        # 'file of calculator app' -> drop connector prefixes from the name
        path = re.sub(r"^(?:of|for|about)\s+", "", path.strip(), flags=re.I).strip()

        # Build final path
        if on_desktop:
            path = os.path.join(self._get_desktop_path(), path.strip())

        # Extension: spoken type wins, else default to .txt
        ext = os.path.splitext(path)[1].lower()
        if path and operation in ("create", "write", "append", "replace"):
            if forced_ext and ext != "." + forced_ext:
                path = os.path.splitext(path)[0] + "." + forced_ext
            elif not ext:
                path += ".txt"

        # Extract old/new for replace operations
        old = ""
        new = ""
        if operation == "replace":
            replace_match = re.search(r"replace\s+(.+?)\s+with\s+(.+?)\s+in", text, re.I)
            if replace_match:
                old = replace_match.group(1).strip()
                new = replace_match.group(2).strip()
        
        return {
            "path": path.strip(),
            "content": content.strip(),
            "on_desktop": on_desktop,
            "old": old.strip(),
            "new": new.strip(),
        }

    def run(self, request: str) -> str:
        # resume a pending op when the user answers with just a location
        if self._pending_op is not None:
            if looks_like_location_answer(request):
                return self._resume_pending(request)
            # different instruction given - drop the stale pending
            self._pending_op = None

        operation = self._classify_operation(request)
        if not operation:
            return "I didn't understand that file operation."

        params = self._extract_parameters(request, operation)
        path = params.get("path", "")
        if not path:
            return f"What would you like me to {operation}?"

        # ask for a destination when creating/writing without one
        if operation in ("create", "write") and not self._has_location(request, path):
            self._pending_op = {"operation": operation, "params": params}
            name = os.path.basename(path)
            return (
                f"Where should I {operation} '{name}'? Say 'on desktop', "
                "'in documents', 'in downloads', an <X> drive, or a full path."
            )

        return self._finalize(operation, path, params, request)

    def _has_location(self, request, path):
        if re.search(r"[\\/]", path) or re.match(r"^[a-z]:", path, re.I):
            return True
        if extract_location(request.lower()):
            return True
        return False

    def _resume_pending(self, request):
        pend = self._pending_op
        self._pending_op = None
        loc = extract_location(request.lower())
        if loc:
            label, base = loc
            if label.lower().startswith("desktop"):
                base = self._get_desktop_path()
        elif re.match(r"^[a-z]:\\", request.strip(), re.I):
            base = request.strip().strip('"')
        else:
            base = self._get_desktop_path()
        params = pend["params"]
        old_path = params.get("path", "")
        params["path"] = os.path.join(base, os.path.basename(old_path))
        return self._finalize(
            pend["operation"], params["path"], params,
            f"{pend['operation']} {params['path']}",
        )

    def _finalize(self, operation, path, params, raw_request):
        level_map = {
            "create": Level.YELLOW,
            "read": Level.GREEN,
            "write": Level.ORANGE,
            "append": Level.YELLOW,
            "replace": Level.ORANGE,
            "delete_file": Level.ORANGE,
            "create_folder": Level.YELLOW,
            "delete_folder": Level.ORANGE,
        }
        level = level_map.get(operation, Level.YELLOW)

        self.policies.allow(f"{self.name}:{operation}:{path}", level)
        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {
                "operation": operation, "path": path, **params
            })
            return f"{operation.capitalize()} {path} needs approval. Say 'approve' to proceed."

        params["raw"] = raw_request
        return self._execute_operation(operation, path, params)

    def _execute_operation(self, operation: str, path: str, params: dict) -> str:
        try:
            if operation == "create":
                result = self._execute_create_file(path, params.get("content", ""))
            elif operation == "write":
                result = self._execute_write(path, params.get("content", ""), overwrite=True)
            elif operation == "append":
                result = self._execute_write(path, params.get("content", ""), overwrite=False)
            elif operation == "replace":
                # Path should already be extracted in params by _extract_parameters
                if path:
                    result = self._execute_replace(path, params.get("old", ""), params.get("new", ""))
                else:
                    # Fallback: extract from raw
                    match = re.search(r"replace\s+(.+?)\s+with\s+(.+?)\s+in\s+(.+?)(?:\s+on\s+desktop|\s*$)", 
                                      params.get("raw", ""), re.I)
                    if match:
                        result = self._execute_replace(match.group(3), match.group(1), match.group(2))
                    else:
                        result = "Usage: replace <old> with <new> in <path>"
            elif operation == "read":
                result = self._execute_read_file(path)
            elif operation == "delete_file":
                result = self._execute_delete_file(path)
            elif operation == "create_folder":
                result = self._execute_create_folder(path)
            elif operation == "delete_folder":
                result = self._execute_delete_folder(path)
            else:
                return f"Unsupported operation: {operation}"
            
            # Log to memory for context
            self._log_operation(operation, path, params, result)
            return result
        except Exception as exc:
            return f"Failed to {operation} {path}: {exc}"

    def _log_operation(self, operation, path, params, result):
        try:
            self.memory.log_action(
                action=f"file_{operation}",
                reason=f"User requested: {params.get('raw', '')}",
                result=result,
                verification="completed" if "Failed" not in result and "not found" not in result else "failed"
            )
        except Exception:
            pass  # Don't break if memory fails

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
            mode = "w" if overwrite else "a+"
            with open(path, mode, encoding="utf-8") as f:
                if not overwrite:
                    # Check if file has content and doesn't end with whitespace
                    f.seek(0, 2)  # Go to end
                    pos = f.tell()
                    if pos > 0:
                        f.seek(pos - 1)
                        last_char = f.read(1)
                        if last_char and not last_char.isspace():
                            f.write(" ")
                f.write(content)
            action = "Overwrote" if overwrite else "Appended to"
            return f"{action} {path} ({len(content)} chars)."
        except Exception as exc:
            return f"Failed to write {path}: {exc}"

    def _execute_read_file(self, path):
        try:
            if not os.path.isfile(path):
                return f"File not found: {path}"
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            preview = content[:2000]
            return f"{path} ({len(content)} chars):\n{preview}"
        except Exception as exc:
            return f"Failed to read {path}: {exc}"

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
        if op == "append":
            return self._execute_write(path, payload.get("content", ""), overwrite=False)
        if op == "replace":
            return self._execute_replace(path, payload.get("old"), payload.get("new"))
        if op == "delete_file":
            return self._execute_delete_file(path)
        if op == "create_folder":
            return self._execute_create_folder(path)
        if op == "delete_folder":
            return self._execute_delete_folder(path)
        return "Unknown operation."