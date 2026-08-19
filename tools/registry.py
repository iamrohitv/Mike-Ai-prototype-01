from tools.computer.note_tool import NoteTool
from tools.computer.project_tool import ProjectTool
from tools.computer.file_tool import FileTool
from tools.computer.task_tool import TaskTool


def build_tools(memory, policies):
    return [
        NoteTool(memory, policies),
        ProjectTool(memory, policies),
        FileTool(memory, policies),
        TaskTool(memory, policies),
    ]