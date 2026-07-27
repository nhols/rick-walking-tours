import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import type { Chapter } from "../types";

const SIGNED_URL_LIFETIME_SECONDS = 60 * 60;
const SIGNED_URL_REFRESH_BUFFER_MS = 60 * 1000;

const signedAudioUrls = new Map<
  string,
  { expiresAt: number; request: Promise<string> }
>();

function getSignedAudioUrl(audioPath: string): Promise<string> {
  const cached = signedAudioUrls.get(audioPath);
  if (cached && cached.expiresAt > Date.now()) return cached.request;

  const request = supabase.storage
    .from("tour-audio")
    .createSignedUrl(audioPath, SIGNED_URL_LIFETIME_SECONDS)
    .then(({ data, error }) => {
      if (error) throw error;
      return data.signedUrl;
    });

  signedAudioUrls.set(audioPath, {
    expiresAt:
      Date.now() +
      SIGNED_URL_LIFETIME_SECONDS * 1000 -
      SIGNED_URL_REFRESH_BUFFER_MS,
    request
  });

  void request.catch(() => {
    if (signedAudioUrls.get(audioPath)?.request === request) {
      signedAudioUrls.delete(audioPath);
    }
  });

  return request;
}

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
      const signedUrl = await getSignedAudioUrl(audioPath);
      if (!cancelled) setSource(signedUrl);
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
  return <audio className="audio-player" controls preload="none" src={source} />;
}
