import { parseRunEvent, type RunEvent } from "../api/events";

/** Parses a finished text/event-stream body into events. Used to rebuild a run's timeline from
 * the server's replayable log; live runs go through EventSource instead. */
export function parseSseText(text: string): RunEvent[] {
  const events: RunEvent[] = [];
  for (const block of text.replaceAll("\r\n", "\n").split("\n\n")) {
    let type = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue; // keep-alive comment
      if (line.startsWith("event:")) type = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length === 0) continue;
    const event = parseRunEvent(type, data.join("\n"));
    if (event) events.push(event);
  }
  return events;
}
