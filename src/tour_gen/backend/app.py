import os
from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from supabase import Client

from tour_gen.backend.artifacts import ArtifactStore, SupabaseArtifactStore
from tour_gen.backend.models import (
    TourApproval,
    TourFeedback,
    TourInput,
    TourRead,
    TourSummary,
)
from tour_gen.backend.repository import (
    InsufficientCreditsError,
    SupabaseTourRepository,
    TourRepository,
    create_supabase_client_from_env,
    tour_to_read,
)
from tour_gen.backend.service import (
    AgentPipeline,
    PipelineRunner,
    PlanMismatchError,
    TourNotFoundError,
    TourStateError,
    approve_and_produce_tour,
    create_and_plan_tour,
    revise_tour_plan,
)
from tour_gen.geo.geoencode import Geocoder
from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder
from tour_gen.tts.gemini import GeminiTTSProvider
from tour_gen.tts.provider import TTSProvider


GeocoderFactory = Callable[[], Geocoder]
TTSProviderFactory = Callable[[], TTSProvider]


def create_app(
    *,
    repository: TourRepository | None = None,
    artifact_store: ArtifactStore | None = None,
    owner_id: UUID | None = None,
    runner: PipelineRunner | None = None,
    geocoder_factory: GeocoderFactory = GoogleMapsGeocoder,
    tts_provider_factory: TTSProviderFactory = GeminiTTSProvider,
) -> FastAPI:
    application = FastAPI(title="Rick Local Tour Worker API")
    application.state.repository = repository
    application.state.supabase_client = None
    application.state.artifact_store = artifact_store
    application.state.owner_id = owner_id
    application.state.runner = runner or AgentPipeline()
    application.state.geocoder_factory = geocoder_factory
    application.state.tts_provider_factory = tts_provider_factory
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post(
        "/tours",
        response_model=TourRead,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_tour(
        payload: TourInput,
        request: Request,
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
    ) -> TourRead:
        try:
            tour = await create_and_plan_tour(
                repository,
                owner_id,
                payload,
                runner=request.app.state.runner,
                geocoder=request.app.state.geocoder_factory(),
            )
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tour planning failed",
            ) from error
        return tour_to_read(repository, tour)

    @application.get("/tours", response_model=list[TourSummary])
    def get_tours(
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
    ) -> list[TourSummary]:
        return repository.list_tours(owner_id)

    @application.get("/tours/{tour_id}", response_model=TourRead)
    def get_tour_detail(
        tour_id: UUID,
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
    ) -> TourRead:
        tour = repository.get_tour(tour_id, owner_id)
        if tour is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return tour_to_read(repository, tour)

    @application.post("/tours/{tour_id}/approve", response_model=TourRead)
    async def approve_tour(
        tour_id: UUID,
        payload: TourApproval,
        request: Request,
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
        artifact_store: ArtifactStore = Depends(get_artifact_store),
    ) -> TourRead:
        try:
            tour = await approve_and_produce_tour(
                repository,
                owner_id,
                tour_id,
                payload.plan_id,
                runner=request.app.state.runner,
                tts_provider=request.app.state.tts_provider_factory(),
                artifact_store=artifact_store,
            )
        except TourNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except (PlanMismatchError, TourStateError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        except InsufficientCreditsError as error:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="You need one credit to create this tour",
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tour production failed",
            ) from error
        return tour_to_read(repository, tour)

    @application.post("/tours/{tour_id}/feedback", response_model=TourRead)
    async def give_tour_feedback(
        tour_id: UUID,
        payload: TourFeedback,
        request: Request,
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
    ) -> TourRead:
        try:
            tour = await revise_tour_plan(
                repository,
                owner_id,
                tour_id,
                payload.plan_id,
                payload.feedback,
                runner=request.app.state.runner,
                geocoder=request.app.state.geocoder_factory(),
            )
        except TourNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except (PlanMismatchError, TourStateError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Tour revision failed",
            ) from error
        return tour_to_read(repository, tour)

    @application.get("/tours/{tour_id}/chapters/{position}/audio")
    def get_chapter_audio(
        tour_id: UUID,
        position: int,
        repository: TourRepository = Depends(get_repository),
        owner_id: UUID = Depends(get_owner_id),
        artifact_store: ArtifactStore = Depends(get_artifact_store),
    ) -> RedirectResponse:
        tour = repository.get_tour(tour_id, owner_id)
        if tour is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        output = repository.get_output(tour_id, tour.approved_plan_id)
        chapter = next(
            (item for item in output.payload.chapters if item.position == position),
            None,
        ) if output else None
        if chapter is None or chapter.audio_path is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return RedirectResponse(artifact_store.create_signed_url(chapter.audio_path))

    return application


def get_repository(request: Request) -> TourRepository:
    repository = request.app.state.repository
    if repository is None:
        client = get_supabase_client(request)
        repository = SupabaseTourRepository(client)
        request.app.state.repository = repository
        if request.app.state.artifact_store is None:
            request.app.state.artifact_store = SupabaseArtifactStore(client)
    return repository


def get_supabase_client(request: Request) -> Client:
    client = request.app.state.supabase_client
    if client is None:
        client = create_supabase_client_from_env()
        request.app.state.supabase_client = client
    return client


def get_artifact_store(request: Request) -> ArtifactStore:
    artifact_store = request.app.state.artifact_store
    if artifact_store is None:
        get_repository(request)
        artifact_store = request.app.state.artifact_store
    if artifact_store is None:
        raise RuntimeError("Artifact store is not configured")
    return artifact_store


def get_owner_id(request: Request) -> UUID:
    owner_id = request.app.state.owner_id
    if owner_id is not None:
        return owner_id

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A Supabase access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = get_supabase_client(request).auth.get_user(token)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Supabase access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Supabase access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UUID(str(response.user.id))


def _cors_origins() -> list[str]:
    configured = os.environ.get("TOUR_GEN_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app = create_app()
