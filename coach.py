import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

from nexon import get_ouid
from analysis import analyze

load_dotenv()

# 라이브러리 내부 재시도는 끄고(attempts=1), 한 번 요청에 최대 30초만 기다림
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=30_000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

# 앞에 적은 모델부터 시도하고, 실패하면 다음 모델로 넘어감
MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.8-flash").split(",") if m.strip()]


def format_tactics(tactics):
    """전술 변경 기록과 전후 비교 결과를 AI가 읽기 쉬운 글로 정리"""
    if not tactics:
        return "(기록 없음)"

    def v(x):
        return "-" if x is None else x

    lines = []
    for t in tactics:  # 최신순
        c = t["compare"]
        head = (f"- {t['change_date'].replace('T', ' ')} | 변경 내용: {t['memo']} "
                f"| 변경 전 {c['before_n']}경기 vs 변경 후 {c['after_n']}경기")
        if c["after_n"] == 0:
            lines.append(head + " | 변경 후 경기 없음 (효과 판단 불가)")
            continue
        if not c["enough"]:
            head += f" | 표본 부족 (각 {c['min_games']}경기 미만, 참고용)"
        changes = ", ".join(f"{r['key']} {v(r['before'])}→{v(r['after'])}" for r in c["rows"])
        lines.append(head + "\n    " + changes)
    return "\n".join(lines)


def build_system_prompt(nickname, report, tactics=None):
    return f"""
너는 FC 온라인 공식경기 유저를 돕는 전술 코치 'FC 에이전트'다.

[규칙]
- 반드시 아래 [분석 데이터]와 [전술 변경 기록]의 수치를 근거로 조언한다. 데이터에 없는 수치는 지어내지 않는다.
- 조언할 때는 "어떤 수치 때문에 → 무엇을 바꿔라" 형태로 근거와 행동을 함께 말한다.
- 게임 안에서 바로 따라 할 수 있게 구체적으로 말한다. (예: 팀 전술의 수비 깊이, 수비 스타일, 개인 전술, 수비할 때의 조작 습관)
- 유저의 현재 설정은 [전술 변경 기록]에 적힌 내용만 알 수 있다. 그 외의 포메이션이나 전술 설정은 추측하지 말고, 필요하면 유저에게 물어본다.
- [전술 변경 기록]이 있으면 그 변경의 효과를 변경 전후 수치로 평가하고, 유지할지 되돌릴지, 다음에 무엇을 추가로 조정할지 제안한다.
- 변경 후 경기가 없거나 표본이 부족한 기록은 효과를 단정하지 말고, 경기를 더 해본 뒤 다시 확인하자고 말한다.
- 한 번에 핵심 2~3가지만 말하고, 답변은 짧고 읽기 쉽게 한국어로 쓴다.
- 데이터로 판단할 수 없는 질문이면 솔직하게 모른다고 하고, 어떤 기록이 더 있으면 판단할 수 있는지 알려준다.

[유저] {nickname}

[분석 데이터] (최근 경기 전체 기준)
{json.dumps(report["stats"], ensure_ascii=False, indent=2)}

[자동으로 찾은 약점]
{chr(10).join("- " + s for s in report["insights"])}

[전술 변경 기록] (최신순, 각 변경 시점 기준 전후 최대 20경기 비교)
{format_tactics(tactics)}
""".strip()


class Coach:
    """대화 기록을 직접 관리해서, 모델이 바뀌어도 대화가 이어지게 함"""

    def __init__(self, nickname, report, tactics=None):
        self.nickname = nickname
        self.system_prompt = build_system_prompt(nickname, report, tactics)
        self.history = []

    def update_context(self, report, tactics=None):
        """대화 내용은 유지하고, 코치가 참고하는 데이터만 최신으로 바꿈"""
        self.system_prompt = build_system_prompt(self.nickname, report, tactics)

    def ask(self, message):
        self.history.append(types.Content(role="user", parts=[types.Part(text=message)]))

        for model in MODELS:
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=self.history,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                    ),
                )
                text = res.text or "(빈 응답)"
                self.history.append(types.Content(role="model", parts=[types.Part(text=text)]))
                return text, model
            except errors.APIError as e:
                print(f"({model} 응답 실패: 오류 {e.code} → 다음 모델로 전환)")
            except Exception as e:
                print(f"({model} 응답 실패: {type(e).__name__} → 다음 모델로 전환)")

        self.history.pop()  # 실패한 질문은 대화 기록에서 제거
        return "지금은 AI 코치가 응답할 수 없습니다. 잠시 후 다시 시도해 주세요.", None


def start_coach(nickname):
    report = analyze(get_ouid(nickname))
    if report is None:
        return None
    return Coach(nickname, report)


if __name__ == "__main__":
    print("사용할 모델 순서:", MODELS)
    nickname = input("닉네임 입력: ")
    coach = start_coach(nickname)
    if coach is None:
        raise SystemExit("저장된 경기가 없습니다. collect.py를 먼저 실행하세요.")

    answer, used = coach.ask("내 최근 경기 데이터를 보고 가장 먼저 고쳐야 할 점을 진단해줘.")
    print(f"\n[FC 에이전트] ({used})")
    print(answer)

    while True:
        q = input("\n[나] ")
        if q.strip().lower() == "q":
            break
        answer, used = coach.ask(q)
        print(f"\n[FC 에이전트] ({used})")
        print(answer)