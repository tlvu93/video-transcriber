import type { TranscriptSegment } from "../types/domain";

export function formatTimeSRT(seconds: number): string {
  const date = new Date(0);
  date.setSeconds(seconds);
  const hhmmss = date.toISOString().slice(11, 19);
  const ms = Math.floor((seconds % 1) * 1000)
    .toString()
    .padStart(3, "0");
  return `${hhmmss},${ms}`;
}

export function formatTimeVTT(seconds: number): string {
  const date = new Date(0);
  date.setSeconds(seconds);
  const hhmmss = date.toISOString().slice(11, 19);
  const ms = Math.floor((seconds % 1) * 1000)
    .toString()
    .padStart(3, "0");
  return `${hhmmss}.${ms}`;
}

export function generateSRT(segments: TranscriptSegment[]): string {
  let srt = "";
  for (const [index, segment] of segments.entries()) {
    srt += `${index + 1}\n`;
    srt += `${formatTimeSRT(segment.start_time)} --> ${formatTimeSRT(
      segment.end_time || segment.start_time + 5
    )}\n`;
    srt += `${segment.text}\n\n`;
  }
  return srt;
}

export function generateVTT(segments: TranscriptSegment[]): string {
  let vtt = "WEBVTT\n\n";
  for (const segment of segments) {
    vtt += `${formatTimeVTT(segment.start_time)} --> ${formatTimeVTT(
      segment.end_time || segment.start_time + 5
    )}\n`;
    vtt += `${segment.text}\n\n`;
  }
  return vtt;
}

export function generateTXT(segments: TranscriptSegment[]): string {
  return segments.map((segment) => segment.text).join(" ");
}

export function downloadFile(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
