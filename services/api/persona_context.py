"""Adapted from Persona Chatbot's CharacterPromptTemplate.render_context_blocks.

Copyright (c) 2025 Tinashe Osewe. MIT License.
Upstream: https://github.com/tinasheosewe/persona-chatbot
Revision: 8b48a8f1ed2c400522caf6edc052cb3d06fc046f
Full license: third_party/persona-chatbot.LICENSE
"""


def render_context_blocks(sections: dict[str, list[str]]) -> str:
    def format_block(title, lines):
        if not lines:
            return None
        bullet_lines = '\n'.join(f'- {line}' for line in lines)
        return f'[{title}]\n{bullet_lines}'

    ordered = [
        ('INTERPRETATION', sections.get('interpretation', [])),
        ('RETRIEVAL PLAN', sections.get('retrieval_plan', [])),
        ('DISAMBIGUATION', sections.get('disambiguation', [])),
        ('SYNTHESIS NOTES', sections.get('synthesis_notes', [])),
        ('RECENT DIALOGUE', sections.get('recent_dialogue', [])),
        ('PAST CONTEXT', sections.get('past_dialogue', [])),
        ('GRAPH FACTS', sections.get('structured_facts', [])),
        ('TEXTUAL EVIDENCE', sections.get('textual_evidence', [])),
    ]
    blocks = [block for title, lines in ordered if (block := format_block(title, lines))]
    return '\n\n'.join(blocks)
