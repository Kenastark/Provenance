"""The operational layer (phase 7): the maintenance queue, the Alert Centre, the
human sign-off gate, idempotent dispatch, and the model-drift monitor.

This package holds operational *domain* logic — ranking, state machines, dispatch
policy, drift metrics — as pure functions over data the ``io`` repository returns.
It may lean on the layers upstream of it (config, grid, trust, graph, models) but,
like those, it never imports the presentation layers (``api``/``report``); the HTTP
surface lives in ``api`` and calls into here.
"""
