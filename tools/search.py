import re
import requests
from urllib.parse import quote

def parse_topic(transcript: str) -> str:
    """The goal here is to extract the topic from the transcript for a Wikipedia search."""
    t = (transcript or "").strip()
    lowers = t.lower()
    prefixes = ["search ", "search for ", "wiki ", "wikipedia ", "lookup ", "look up ", "tell me about "]
    topic = t
    for p in prefixes:
        if lowers.startswith(p):
            topic = t[len(p):]
            break
    topic = re.sub(r"[.!?]+$", "", topic).strip()
    topic = re.sub(r"\s+", " ", topic)
    # return the extracted topic
    return topic

def wiki_summary(raw_topic: str):
    """The goal here is to get a Wikipedia summary of the topic."""
    topic = parse_topic(raw_topic)
    if not topic:
        return []

    # encode safely for Wikipedia REST
    topic_encoded = quote(topic.replace(" ", "_"), safe="()_'")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic_encoded}"
    
    # we do this logic, so we catch exceptions, it's a best practice
    try:
        r = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "voice-agent/0.1"},
        )
        if not r.ok:
            return []
        j = r.json()
        if "extract" in j:
            return [{"title": j.get("title", topic), "summary": j["extract"]}]
    except Exception as e:
        print(e)
        return []
    return []
