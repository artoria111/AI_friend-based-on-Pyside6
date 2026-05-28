"""Function-calling tool definitions and executor."""

import json
from datetime import datetime
from typing import Optional


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_memory",
            "description": "当用户要求你「记住」「记下」「备忘」某事时调用。将关于用户的事实存入长期记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "要记住的简洁事实，例如「用户喜欢喝红茶」「用户下周五要交论文」"
                    }
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": "当用户要求你在指定时间后提醒他做某事时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "倒计时秒数。1分钟=60，1小时=3600"
                    },
                    "message": {
                        "type": "string",
                        "description": "提醒内容，例如「喝水」「开会」"
                    }
                },
                "required": ["seconds", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "搜索长期记忆，获取关于用户的事实和过往对话。当你需要了解用户偏好、习惯、之前聊过的话题时主动调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如「饮品偏好」「生日」「正在学什么」"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_mood",
            "description": "当感知到主人的情绪变化时调用。根据主人的话语内容、语气、用词来判断情绪状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": ["happy", "excited", "sad", "worried", "angry", "tired", "bored", "neutral"],
                        "description": "主人的当前情绪"
                    },
                    "reason": {
                        "type": "string",
                        "description": "判断依据，例如「主人说今天涨工资了」「主人看起来很累」"
                    }
                },
                "required": ["mood"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间。当用户询问时间、日期，或需要基于当前时间回答问题时调用。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


def execute(name: str, args: dict, memory_manager=None, alarm_callback=None, mood_tracker=None) -> str:
    """Execute a tool call and return the result as a JSON string."""

    if name == "write_memory":
        fact = args.get("fact", "").strip()
        if fact and memory_manager:
            memory_manager.add_fact(fact)
            print(f"[Tool] write_memory: {fact}")
            return json.dumps({"ok": True, "saved": fact}, ensure_ascii=False)
        return json.dumps({"ok": False, "error": "事实内容为空"}, ensure_ascii=False)

    elif name == "set_alarm":
        seconds = args.get("seconds", 0)
        message = args.get("message", "").strip()
        if seconds <= 0:
            return json.dumps({"ok": False, "error": "时间必须大于0"}, ensure_ascii=False)
        if alarm_callback:
            alarm_callback(seconds, message)
        print(f"[Tool] set_alarm: {seconds}s -> {message}")
        return json.dumps(
            {"ok": True, "seconds": seconds, "message": message},
            ensure_ascii=False
        )

    elif name == "search_memory":
        query = args.get("query", "").strip()
        if not query or not memory_manager:
            return json.dumps({"found": False, "results": []}, ensure_ascii=False)
        retrieval = memory_manager.retrieve_all(query)
        facts = retrieval.get("facts", [])
        episodes = retrieval.get("episodes", [])
        print(f"[Tool] search_memory('{query}') -> facts:{facts}, episodes:{episodes}")
        return json.dumps(
            {"found": bool(facts or episodes), "facts": facts, "episodes": episodes},
            ensure_ascii=False
        )

    elif name == "set_mood":
        mood = args.get("mood", "").strip().lower()
        reason = args.get("reason", "").strip()
        valid_moods = {"happy", "excited", "sad", "worried", "angry", "tired", "bored", "neutral"}
        if mood not in valid_moods:
            return json.dumps({"ok": False, "error": f"无效情绪: {mood}"}, ensure_ascii=False)
        if mood_tracker:
            mood_tracker.record(mood, reason)
        print(f"[Tool] set_mood: {mood}" + (f" (原因: {reason})" if reason else ""))
        return json.dumps({"ok": True, "mood": mood}, ensure_ascii=False)

    elif name == "get_time":
        now = datetime.now()
        result = {
            "datetime": now.strftime("%Y年%m月%d日 %H:%M"),
            "weekday": now.strftime("%A"),
            "timestamp": now.isoformat()
        }
        print(f"[Tool] get_time -> {result['datetime']}")
        return json.dumps(result, ensure_ascii=False)

    else:
        return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
