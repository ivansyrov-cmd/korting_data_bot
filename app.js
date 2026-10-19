"use strict";

const { spawn } = require("child_process");

const root = __dirname;
const commands = process.platform === "win32" ? ["python"] : ["python3", "python"];

function run(index) {
  const cmd = commands[index];
  if (!cmd) {
    console.error("python not found");
    process.exit(1);
  }
  const child = spawn(cmd, ["main.py"], {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  });
  child.on("error", (err) => {
    if (err.code === "ENOENT" && index + 1 < commands.length) {
      run(index + 1);
      return;
    }
    console.error(err);
    process.exit(1);
  });
  child.on("exit", (code, signal) => {
    if (signal) process.exit(1);
    process.exit(code ?? 1);
  });
}

run(0);
