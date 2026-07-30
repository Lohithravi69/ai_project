import * as vscode from "vscode";

const CLI = "aidev";

function runInTerminal(args: string, name = "aidev") {
  const terminal = vscode.window.createTerminal(name);
  terminal.show();
  terminal.sendText(`${CLI} ${args}`);
}

function openInBrowser(path: string) {
  const url = (process.env.AIDEV_URL || "http://localhost:8000") + path;
  vscode.env.openExternal(vscode.Uri.parse(url));
}

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("aidex.brief", () => runInTerminal("brief")),
    vscode.commands.registerCommand("aidex.status", () => runInTerminal("status")),
    vscode.commands.registerCommand("aidex.plan", async () => {
      const objective = await vscode.window.showInputBox({ prompt: "Plan objective", placeHolder: "e.g. Add dark mode toggle" });
      if (objective) runInTerminal(`plan "${objective}"`);
    }),
    vscode.commands.registerCommand("aidex.task", async () => {
      const objective = await vscode.window.showInputBox({ prompt: "Task objective", placeHolder: "e.g. Refactor auth module" });
      if (objective) runInTerminal(`task "${objective}"`);
    }),
    vscode.commands.registerCommand("aidex.recommendations", () => runInTerminal("recommendations")),
    vscode.commands.registerCommand("aidex.logs", () => runInTerminal("logs")),
    vscode.commands.registerCommand("aidex.repos", () => runInTerminal("repos")),
    vscode.commands.registerCommand("aidex.report", () => runInTerminal("report --latest")),
    vscode.commands.registerCommand("aidex.openPortfolio", () => openInBrowser("/portfolio")),
  );

  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = "$(graph) aidev";
  statusBar.tooltip = "AI Dev OS — click for brief";
  statusBar.command = "aidex.brief";
  statusBar.show();
  context.subscriptions.push(statusBar);
}

export function deactivate() {}
