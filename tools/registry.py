from tools.computer.note_tool import NoteTool
from tools.computer.project_tool import ProjectTool
from tools.computer.file_tool import FileTool
from tools.computer.file_ops_tool import FileOpsTool
from tools.computer.launch_tool import LaunchTool
from tools.computer.task_tool import TaskTool
from tools.computer.terminal_tool import TerminalTool
from tools.computer.git_tool import GitTool
from tools.computer.system_tool import SystemTool
from tools.computer.screenshot_tool import ScreenshotTool
from tools.computer.open_app_tool import OpenAppTool


def build_tools(memory, policies):
    return [
        NoteTool(memory, policies),
        ProjectTool(memory, policies),
        FileOpsTool(memory, policies),
        FileTool(memory, policies),
        LaunchTool(memory, policies),
        TaskTool(memory, policies),
        TerminalTool(memory, policies),
        GitTool(memory, policies),
        SystemTool(memory, policies),
        ScreenshotTool(memory, policies),
        OpenAppTool(memory, policies),
    ]