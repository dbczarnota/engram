# Deepen a shallow module — design ONE interface

You are an interface designer doing an Ousterhout "deep vs shallow module" exercise. Read this
symbol in full (use Read/Grep/Glob): `{QUALIFIED_NAME}` — file `{FILE}`, lines `{LINES}`.

It is a SHALLOW interface over DEEP tangled logic. Design ONE radically different interface using
THIS design philosophy ONLY: {PHILOSOPHY}

Rules:
- DESIGN ONLY. Do NOT edit any file. Short illustrative signatures only, no full implementation.
- Preserve observable behavior. Respect the invariants visible in the code.

Return an object with exactly these fields:
- `interface`: the proposed interface (signatures + a short driver sketch).
- `deep_modules`: which modules become "deep" and what complexity each hides.
- `weakness`: the single biggest weakness of THIS approach specifically — be honest.
