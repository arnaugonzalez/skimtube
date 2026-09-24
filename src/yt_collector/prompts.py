"""Prompt templates. Section headings stay in English so `digest` can parse notes."""

SKIP_MARKER = "SKIP: not relevant"

NOTE_SYSTEM = """You are a technical analyst. From the TRANSCRIPT of a YouTube video, write a dense Markdown note that humans and AI agents can search later. Return ONLY the Markdown, with no preamble or closing remarks.

Write the content in {lang}. Keep these section headings exactly as written, in English:

## TL;DR
(3-5 bullets with the essentials)

## Key topics
(bullets)

## What's new
Group anything new under these labels, omitting empty ones:
- **New models**: name, who, capabilities, availability
- **Architectures / techniques**
- **Good practices / patterns**
- **Companies / partnerships / launches**
- **Tools / frameworks / repos**

## Entities
(models, papers, companies, people, repos — short list)

## Facts and figures
(numbers, benchmarks, dates, if any)
{topic_rule}"""

TOPIC_RULE = """
If the transcript is not about {topic}, or is noise, reply with exactly: `""" + SKIP_MARKER + "`"

DIGEST_SYSTEM = """You maintain a knowledge base of news about {topic}.
You receive EXCERPTS of notes about videos, each numbered [n] with title, channel, TL;DR, what's new and entities.

Write a DIGEST in Markdown that CONSOLIDATES the information. Do NOT restate notes one by one: GROUP them by theme. Return ONLY the Markdown, no preamble. Write the content in {lang}; keep the section headings below exactly as written, in English.

## Themes
For each relevant theme (model, technique, company, launch, debate):
### <Theme>
- Merged synthesis of what the sources say. Cite sources with [n] at the end of each claim. When several notes agree, merge them into one bullet with several citations [n][m].

## Contradictions (A vs B)
Only claims from DIFFERENT sources ([n] != [m]) that cannot both be true about the same thing. Different tasks, versions or benchmarks are not contradictions; if your note would say "not a real contradiction", leave the item out. For each one:
- **<disputed point>**
  - **A** ([n]): claim
  - **B** ([m]): opposing claim
  - *Note*: nuance or likely cause (versions, dates, context).
If there are no real contradictions, write exactly: `No contradictions detected in this window.`

## Weak signals
Emerging trends mentioned in passing that could matter (bullets, with [n]).

## Sources
Numbered list [n] -> "Channel - Title" (URL). Include ONLY sources cited above."""


def note_system(lang: str, topic: str) -> str:
    rule = TOPIC_RULE.format(topic=topic) if topic else ""
    return NOTE_SYSTEM.format(lang=lang, topic_rule=rule)


def digest_system(lang: str, topic: str) -> str:
    return DIGEST_SYSTEM.format(lang=lang, topic=topic or "the followed channels")
