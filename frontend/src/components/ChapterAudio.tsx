import { useEffect, useState } from "react";
import { getChapterAudio } from "../lib/offline";
import { useOnlineStatus } from "../lib/online";
import { supabase } from "../lib/supabase";
import type { Chapter } from "../types";

export function ChapterAudio({ chapter }: { chapter: Chapter }) {
  const [source, setSource] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const online = useOnlineStatus();
  const chapterId = chapter.id;
  const audioPath = chapter.audio_path;

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setSource(null);
    setError(null);

    async function loadAudio() {
      const downloaded = await getChapterAudio(chapterId);
      if (downloaded) {
        const url = URL.createObjectURL(downloaded);
        if (cancelled) {
          URL.revokeObjectURL(url);
        } else {
          objectUrl = url;
          setSource(url);
        }
        return;
      }
      if (!audioPath) {
        if (!cancelled) setError("Audio unavailable.");
        return;
      }
      if (!online) {
        if (!cancelled) setError("Download this tour before listening offline.");
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
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [chapterId, audioPath, online]);

  if (error) return <p className="inline-notice">{error}</p>;
  if (!source) return <div className="audio-skeleton">Loading audio…</div>;
  return <audio className="audio-player" controls preload="metadata" src={source} />;
}
