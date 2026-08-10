import { execFile, execFileSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const lifecycle = join(homedir(), ".ai-console", "bin", "ai-console-lifecycle");
const injectedSessions = new Set();

function input(event, directory) {
  const properties = event?.properties ?? {};
  return JSON.stringify({
    cwd: directory,
    hookEventName: event?.type,
    sessionId: properties.sessionID ?? properties.info?.id,
    reason: event?.type,
  });
}

function capture(event, directory, name) {
  execFile(
    lifecycle,
    ["capture", "opencode", name],
    { input: input(event, directory), timeout: 1200 },
    () => {},
  );
}

export const AiConsoleLifecyclePlugin = async ({ directory }) => ({
  "experimental.chat.system.transform": async ({ sessionID }, output) => {
    if (sessionID && injectedSessions.has(sessionID)) return;
    try {
      const brief = execFileSync(lifecycle, ["brief", "opencode"], {
        input: JSON.stringify({ cwd: directory, sessionId: sessionID }),
        encoding: "utf8",
        timeout: 1200,
      }).trim();
      if (brief) output.system.push(brief);
      if (sessionID) injectedSessions.add(sessionID);
    } catch {
      // Lifecycle integration is advisory and must fail open.
    }
  },
  event: async ({ event }) => {
    if (event?.type === "session.created") capture(event, directory, "session-start");
    if (event?.type === "session.idle") capture(event, directory, "stop");
    if (event?.type === "session.deleted") {
      capture(event, directory, "session-end");
      const id = event?.properties?.sessionID ?? event?.properties?.info?.id;
      if (id) injectedSessions.delete(id);
    }
  },
});
