# Tour Generation Pipeline

Build the pipeline one step at a time. Each agent should have a small job,
typed inputs, typed outputs, and clear non-goals.

## 1. Checkpoint Research Agent

Purpose: propose good walking-tour checkpoint candidates for a user request.

Input:

```python
user_request: str
```

Example:

```text
Harry Potter themed walking tour in Edinburgh, under 5km
```

Output:

```python
class CheckpointProposal(BaseModel):
    title: str
    brief_description: str
    lat: float
    lon: float


class CheckpointResearchOutput(BaseModel):
    proposals: list[CheckpointProposal]
```

Responsibilities:

- Understand the requested location, theme, and rough constraints from the
  free-form string.
- Research plausible physical checkpoints for the tour.
- Geocode each proposed checkpoint.
- Return only checkpoints with latitude and longitude.
- Keep descriptions brief and useful for a shortlist/map view.

Useful tools:

- Web search or browsing for research.
- Geocoder for turning checkpoint names into latitude and longitude.

Non-goals:

- Do not plan the route.
- Do not write chapter scripts.
- Do not generate audio.
- Do not create quizzes.

## 2. Checkpoint Review

Purpose: let the user curate the proposed checkpoints before route planning or
content generation begins.

User experience:

- Show proposed checkpoints on a map.
- Let the user confirm all checkpoints.
- Let the user select a subset of checkpoints.
- Let the user respond with feedback for another research pass.

Responsibilities:

- Preserve the user's confirmed checkpoint choices.
- Capture free-form feedback clearly enough for the checkpoint research agent
  to revise its proposals.
- Avoid moving forward until there is a confirmed set of checkpoints.

Non-goals:

- Do not plan the route.
- Do not write chapter scripts.
- Do not generate audio.

## 3. Route Planner Agent

Purpose: order the confirmed checkpoints into a walkable sequence that makes
sense logistically and narratively.

Input:

```python
user_request: str
confirmed_checkpoints: list[CheckpointProposal]
```

Output:

```python
class OrderedCheckpoint(BaseModel):
    checkpoint: CheckpointProposal
    order: int
    route_reasoning: str


class RoutePlan(BaseModel):
    ordered_checkpoints: list[OrderedCheckpoint]
    total_distance_m: int | None
    estimated_walking_time_min: int | None
    route_warnings: list[str]
```

Responsibilities:

- Order checkpoints using walking logistics and narrative continuity.
- Prefer a satisfying beginning, middle, and ending where the theme supports it.
- Check that a walking route exists between consecutive checkpoints.
- Check obvious user constraints, such as maximum distance or rough duration.
- Return warnings if constraints cannot be satisfied cleanly.

Example narrative logic:

- For a Harry Potter tour in Edinburgh, it may make sense to start near a cafe
  associated with early writing and end near the hotel associated with finishing
  the final book.

Useful tools:

- Map view or coordinate list.
- Walking directions provider.
- Distance matrix provider.

Non-goals:

- Do not write chapter scripts.
- Do not generate audio.
- Do not add new checkpoints unless asked to repair an impossible route.

## 4. Chapter Writer Agent

Purpose: write the spoken chapter for each ordered checkpoint.

Input:

```python
user_request: str
route_plan: RoutePlan
```

Output:

```python
class Chapter(BaseModel):
    checkpoint_title: str
    order: int
    script: str
    estimated_duration_seconds: int | None


class ChapterWritingOutput(BaseModel):
    chapters: list[Chapter]
```

Responsibilities:

- Write one chapter per checkpoint.
- Match the requested theme, audience, and tone.
- Make each chapter sound natural when spoken aloud.
- Give each chapter a clear connection to the previous and next stop.
- Keep scripts concise enough for a walking tour.

Non-goals:

- Do not change checkpoint order.
- Do not generate audio.
- Do not create quizzes.

## 5. Quiz Generator Agent

Purpose: create a short multiple-choice quiz for each stop.

Input:

```python
chapters: list[Chapter]
```

Output:

```python
class QuizQuestion(BaseModel):
    question: str
    choices: list[str]
    correct_choice_index: int
    explanation: str | None = None


class StopQuiz(BaseModel):
    checkpoint_title: str
    order: int
    questions: list[QuizQuestion]
```

Responsibilities:

- Create one quiz per stop.
- Generate 3-7 multiple-choice questions per quiz to begin with.
- Keep questions answerable from that stop's chapter.
- Avoid trick questions and ambiguous answers.

Non-goals:

- Do not introduce new facts not present in the chapters.
- Do not rewrite chapter scripts.

## 6. Narrator

Purpose: convert chapter scripts into speech.

Input:

```python
chapters: list[Chapter]
```

Output:

```python
class NarratedChapter(BaseModel):
    checkpoint_title: str
    order: int
    script: str
    audio_asset_url: str
    audio_duration_seconds: int | None
```

Responsibilities:

- Convert each chapter script to speech.
- Preserve chapter order.
- Return stable references to generated audio assets.
- Keep the script as the canonical source of truth.

Non-goals:

- Do not rewrite chapters.
- Do not choose or reorder checkpoints.

## 7. Tour Assembly

Purpose: assemble the route, chapters, quizzes, and audio into one tour object.

Input:

```python
route_plan: RoutePlan
narrated_chapters: list[NarratedChapter]
quizzes: list[StopQuiz]
```

Output:

```python
class Tour(BaseModel):
    title: str
    route_plan: RoutePlan
    chapters: list[NarratedChapter]
    quizzes: list[StopQuiz]
```

Responsibilities:

- Ensure every ordered checkpoint has a chapter.
- Ensure every ordered checkpoint has a quiz.
- Ensure every chapter has an audio asset.
- Produce the object the app can display, download, and play.

Non-goals:

- Do not invent missing route, chapter, quiz, or audio content.
