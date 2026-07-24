import { openDB, type DBSchema } from "idb";
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

const database = openDB<RickOfflineDB>("rick-offline", 1, {
  upgrade(db) {
    db.createObjectStore("tours", { keyPath: "tourId" });
    db.createObjectStore("audio", { keyPath: "chapterId" });
  }
});

export async function getDownloadedTours(): Promise<DownloadedTour[]> {
  return (await database).getAll("tours");
}

export async function getDownloadedTour(
  tourId: string
): Promise<DownloadedTour | undefined> {
  return (await database).get("tours", tourId);
}

export async function saveDownloadedTour(bundle: TourBundle): Promise<void> {
  await (await database).put("tours", {
    tourId: bundle.tour.id,
    bundle,
    savedAt: new Date().toISOString()
  });
}

export async function saveChapterAudio(
  chapterId: string,
  blob: Blob
): Promise<void> {
  await (await database).put("audio", { chapterId, blob });
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
