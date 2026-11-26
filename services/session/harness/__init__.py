"""The persona prompt harness (#67): scripted synthetic runs and their checks.

A dev-only package beside ``cst_session``. The service image copies only
``cst_session``, so none of this ships. ``python -m harness.run`` drives each
script through the real session lifecycle and the real persona adapter, and
prints check results only: never a reply, a prompt or a script turn (FR-5).
"""
