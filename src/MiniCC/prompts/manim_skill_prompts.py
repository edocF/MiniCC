"""Manim capability prompt for MiniCC visual math agents."""

MANIM_CAPABILITY_PROMPT = """MANIM CAPABILITY SKILL

Use this as the capability boundary when planning scripts, storyboards, or code for Manim.

Manim is best for:
- Step-by-step mathematical explanation videos.
- Geometry transformations, movement, highlighting, and construction.
- Formula progression, labels, braces, arrows, number lines, axes, plots, and probability diagrams.
- Classroom-style animation with captions, timing, visual emphasis, and scene transitions.

Prefer Manim when:
- The user wants a video rather than browser interaction.
- The explanation benefits from timed narration, staged reveal, or camera-like pacing.
- The math is about transformation, distribution, graph evolution, geometric reasoning, or formula derivation.

Avoid Manim when:
- The user needs direct browser interaction, sliders, dragging, or real-time controls. Prefer Canvas or JSXGraph.
- The visual must be a lightweight standalone HTML artifact.
- The task mainly needs precise interactive graph exploration. Prefer JSXGraph.

Implementation constraints:
- Generate exactly one Python file for one complete visual explanation under outputs/manim, unless the user explicitly asks for multi-file output.
- Define exactly one clear Scene class unless the user asks for multiple scenes.
- Do not put all logic directly inside construct().
- Code order should be: imports/constants/helper functions, Scene class helper methods, one method per storyboard scene, then construct() at the end of the Scene class.
- construct() must be a high-level scheduler only: call the per-storyboard methods in order, with minimal logic inside construct().
- Each storyboard scene must map to one rich Scene method, for example scene_intro(), scene_build_model(), scene_formula_meaning(), scene_summary().
- Each scene method should contain multiple visible beats: title/caption, object creation, at least one animated change, math label/formula/relationship, and a short summary or transition.
- If a storyboard scene includes shots, implement those shots as clearly separated blocks or helper methods inside the corresponding scene method.
- Prefer Text for Chinese text and simple labels to avoid LaTeX dependency problems.
- Use MathTex only when LaTeX availability is known or the formula is essential.
- Keep objects readable: font sizes, colors, spacing, and screen boundaries matter.
- Use helper methods for repeated objects such as axes, caption boxes, formula cards, counters, character icons, bars, or probability tables.
- Avoid excessive simultaneous animations; staged reveal is easier to understand.
- Include captions or text labels that connect each visual action to the math meaning.
- Use deterministic values or seeded randomness when illustrating distributions or simulations.

Verification expectations:
- Import the scene class if rendering is expensive.
- Render a low-quality preview when possible.
- If rendering fails, repair the smallest cause first: imports, text, layout, object names, or unsupported API usage.
- Do not claim a video exists unless the file was actually rendered or found.
"""
