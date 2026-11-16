"""Evaluate stored candidates and rank validated results in application code."""

from slothxiv.agents.claude import ClaudeCLIAgent
from slothxiv.config import Profile
from slothxiv.evaluation import AgentResponse, EvaluationAgent, RankedEntry, Ranking
from slothxiv.evaluation.prompts import PROMPT_VERSION, build_request, reuse_key
from slothxiv.models import Paper
from slothxiv.storage.evaluations import EvaluationStore


class RankError(RuntimeError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"ranking failed (run {run_id}); successful evaluations are preserved")


def revision_key(paper: Paper) -> tuple:
    revision = paper.revision
    # arXiv and other decimal revisions compare numerically, never as '9' > '10'.
    return (paper.updated_at, revision.isdecimal(),
            int(revision) if revision.isdecimal() else revision)


def select_candidates(papers: list[Paper], limit: int | None = None) -> list[Paper]:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer")
    latest: dict[str, Paper] = {}
    for paper in papers:
        old = latest.get(paper.paper_id)
        if old is None or revision_key(paper) > revision_key(old):
            latest[paper.paper_id] = paper
    ordered = sorted(latest.values(), key=lambda p: (-p.updated_at.timestamp(), p.paper_id))
    return ordered[:limit]


def rank(profile_name: str, profile: Profile, store: EvaluationStore, *,
         agent: EvaluationAgent | None = None, limit: int | None = None,
         force: bool = False) -> Ranking:
    settings = profile.evaluation
    if settings is None:
        raise ValueError("profile requires [profiles.<name>.evaluation] instructions for ranking")
    adapter = agent if agent is not None else ClaudeCLIAgent(settings.model, settings.timeout_seconds)
    candidates = select_candidates(store.list_papers(profile_name), limit)
    identity = dict(adapter.identity)
    run_id = store.start_evaluation_run(profile_name, profile, identity, PROMPT_VERSION,
                                        len(candidates), {"limit": limit, "force": force})
    entries: list[RankedEntry] = []
    failures: dict[str, str] = {}
    active: str | None = None
    try:
        for paper in candidates:
            request = build_request(paper, settings.instructions)
            key = reuse_key(request, identity)
            record = None if force else store.find_evaluation(key)
            reused = record is not None
            if record is None:
                active = store.start_evaluation(run_id, key, request)
                try:
                    response = AgentResponse.model_validate(adapter.evaluate(request))
                    if (response.result.paper_id, response.result.revision) != (paper.paper_id, paper.revision):
                        raise ValueError("agent returned mismatched paper identity/revision")
                except Exception as error:
                    detail = f"{type(error).__name__}: {error}"
                    store.fail_evaluation(active, detail)
                    active = None
                    failures[paper.paper_id] = detail
                    continue
                record = store.complete_evaluation(active, response)
                active = None
            store.link_evaluation(run_id, record, reused)
            entries.append(RankedEntry(evaluation=record, reused=reused))
        store.finish_evaluation_run(run_id, f"{len(failures)} candidate(s) failed" if failures else None)
    except BaseException as error:
        try:
            if active is not None:
                store.fail_evaluation(active, f"{type(error).__name__}: {error}")
            store.finish_evaluation_run(run_id, f"{type(error).__name__}: {error}")
        except Exception as recording_error:
            error.add_note(f"Could not record evaluation failure: {recording_error}")
        if not isinstance(error, Exception):
            raise
        raise RankError(run_id) from error
    entries.sort(key=lambda entry: (
        -entry.evaluation.response.result.score,
        -entry.evaluation.paper.updated_at.timestamp(), entry.evaluation.paper.paper_id,
    ))
    return Ranking(run=store.get_evaluation_run(run_id), entries=tuple(entries), failures=failures)
