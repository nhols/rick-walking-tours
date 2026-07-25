import { openDB, type DBSchema } from "idb";
import { loadTourBundle, supabase } from "./supabase";
import type { DownloadedTour, TourBundle } from "../types";

interface RickOfflineDB extends DBSchema {
  tours: {
    key: string;
    value: DownloadedTour;
  };
  audio: {
    key: string;
    value: {
      chapterId: string;
      blob: Blob;
    };
  };
}

const database = openDB<RickOfflineDB>("rick-offline", 2, {
  upgrade(db, oldVersion, _newVersion, transaction) {
    if (oldVersion === 0) {
      db.createObjectStore("tours", { keyPath: "tourId" });
      db.createObjectStore("audio", { keyPath: "chapterId" });
      return;
    }
    transaction.objectStore("tours").clear();
    transaction.objectStore("audio").clear();
  }
});

export async function getDownloadedTours(): Promise<DownloadedTour[]> {
  return (await database).getAll("tours");
}

export async function downloadTourForOffline(
  tourId: string
): Promise<DownloadedTour> {
  const bundle = await loadTourBundle(tourId);
  const audio: { chapterId: string; blob: Blob }[] = [];
  for (const chapter of bundle.chapters) {
    if (!chapter.audio_path) continue;
    const { data, error } = await supabase.storage
      .from("tour-audio")
      .download(chapter.audio_path);
    if (error) throw error;
    audio.push({ chapterId: chapter.id, blob: data });
  }

  const downloaded = {
    tourId: bundle.tour.id,
    bundle
  };
  const db = await database;
  const transaction = db.transaction(["tours", "audio"], "readwrite");
  await Promise.all([
    transaction.objectStore("tours").put(downloaded),
    ...audio.map((item) => transaction.objectStore("audio").put(item))
  ]);
  await transaction.done;
  return downloaded;
}

export async function getChapterAudio(
  chapterId: string
): Promise<Blob | undefined> {
  return (await database).get("audio", chapterId).then((entry) => entry?.blob);
}

export async function removeDownloadedTour(tourId: string): Promise<void> {
  const db = await database;
  const downloaded = await db.get("tours", tourId);
  if (!downloaded) return;

  const transaction = db.transaction(["tours", "audio"], "readwrite");
  await Promise.all([
    transaction.objectStore("tours").delete(tourId),
    ...downloaded.bundle.chapters.map((chapter) =>
      transaction.objectStore("audio").delete(chapter.id)
    ),
  ]);
  await transaction.done;
}
