import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import type { Chapter } from "../types";

export function ChapterAudio({ chapter }: { chapter: Chapter }) {
  const [source, setSource] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chapterId = chapter.id;
  const audioPath = chapter.audio_path;

  useEffect(() => {
    let cancelled = false;
    setSource(null);
    setError(null);

    async function loadAudio() {
      if (!audioPath) {
        if (!cancelled) setError("Audio unavailable.");
        return;
      }
      const { data, error: signedUrlError } = await supabase.storage
        .from("tour-audio")
        .createSignedUrl(audioPath, 60 * 60);
      if (signedUrlError) throw signedUrlError;
      if (!cancelled) setSource(data.signedUrl);
    }

    loadAudio().catch((audioError: unknown) => {
      if (!cancelled) {
        setError(audioError instanceof Error ? audioError.message : "Audio unavailable");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [chapterId, audioPath]);

  if (error) return <p className="inline-notice">{error}</p>;
  if (!source) return <div className="audio-skeleton">Loading audio…</div>;
  return <audio className="audio-player" controls preload="metadata" src={source} />;
}
