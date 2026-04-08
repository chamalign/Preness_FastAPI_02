"""Mock (模擬試験) の DB 保存サービス."""
from typing import Any, Dict, List, Optional

from app.db import get_db
from app.db.models import Mock, MockPart, MockQuestion, MockQuestionSet, MockSection
from app.schemas.mocks import MockCreate


def _scripts_for_db(scripts: Any) -> Any:
    """Pydantic ScriptTurn または dict のリストを JSON 保存用の list[dict] にする."""
    if scripts is None:
        return None
    out: List[Any] = []
    for t in scripts:
        if hasattr(t, "model_dump"):
            out.append(t.model_dump())
        elif isinstance(t, dict):
            out.append(t)
        else:
            out.append(dict(t))
    return out


def _mock_orm_to_dict(mock: Mock) -> Dict[str, Any]:
    """ORM Mock を API レスポンス用の辞書（MockCreate 同形）に変換."""
    sections = []
    for s in mock.sections:
        parts = []
        for p in s.parts:
            question_sets = []
            for qs in p.question_sets:
                questions = []
                for q in qs.questions:
                    questions.append({
                        "display_order": q.display_order,
                        "question_text": q.question_text,
                        "question_audio_url": q.audio_url,
                        "choice_a": q.choice_a,
                        "choice_b": q.choice_b,
                        "choice_c": q.choice_c,
                        "choice_d": q.choice_d,
                        "correct_choice": q.correct_choice,
                        "explanation": q.explanation,
                        "tag": q.tag,
                        "wrong_reason_a": q.wrong_reason_a,
                        "wrong_reason_b": q.wrong_reason_b,
                        "wrong_reason_c": q.wrong_reason_c,
                        "wrong_reason_d": q.wrong_reason_d,
                        "scripts": q.scripts,
                    })
                question_sets.append({
                    "display_order": qs.display_order,
                    "passage": qs.passage,
                    "conversation_audio_url": qs.audio_url,
                    "questions": questions,
                })
            parts.append({
                "part_type": p.part_type,
                "display_order": p.display_order,
                "question_sets": question_sets,
            })
        sections.append({
            "section_type": s.section_type,
            "display_order": s.display_order,
            "parts": parts,
        })
    return {"title": mock.title, "sections": sections}


def list_mocks(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Mock 一覧を id 降順で返す."""
    with get_db() as session:
        rows = (
            session.query(Mock)
            .order_by(Mock.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [{"id": m.id, "title": m.title} for m in rows]


def get_mock_by_id(mock_id: int) -> Optional[Dict[str, Any]]:
    """mock_id で 1 件取得. 存在しなければ None."""
    with get_db() as session:
        mock = session.get(Mock, mock_id)
        if mock is None:
            return None
        return _mock_orm_to_dict(mock)


def create_mock_from_payload(payload: MockCreate) -> int:
    """
    MockCreate を DB に保存し、発番した mock_id を返す.
    """
    with get_db() as session:
        mock = Mock(title=payload.title)
        session.add(mock)
        session.flush()
        mock_id = mock.id

        for sect in payload.sections:
            ms = MockSection(
                mock_id=mock_id,
                section_type=sect.section_type,
                display_order=sect.display_order,
            )
            session.add(ms)
            session.flush()

            for part in sect.parts:
                mp = MockPart(
                    mock_section_id=ms.id,
                    part_type=part.part_type,
                    display_order=part.display_order,
                )
                session.add(mp)
                session.flush()

                for qs in part.question_sets:
                    mqs = MockQuestionSet(
                        mock_part_id=mp.id,
                        display_order=qs.display_order,
                        passage=qs.passage,
                        audio_url=qs.conversation_audio_url,
                    )
                    session.add(mqs)
                    session.flush()

                    for q in qs.questions:
                        mq = MockQuestion(
                            mock_question_set_id=mqs.id,
                            display_order=q.display_order,
                            question_text=q.question_text,
                            audio_url=q.question_audio_url,
                            choice_a=q.choice_a,
                            choice_b=q.choice_b,
                            choice_c=q.choice_c,
                            choice_d=q.choice_d,
                            correct_choice=q.correct_choice,
                            explanation=q.explanation,
                            tag=q.tag,
                            wrong_reason_a=q.wrong_reason_a,
                            wrong_reason_b=q.wrong_reason_b,
                            wrong_reason_c=q.wrong_reason_c,
                            wrong_reason_d=q.wrong_reason_d,
                            scripts=_scripts_for_db(q.scripts),
                        )
                        session.add(mq)

    return mock_id
