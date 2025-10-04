from services.protos import evaluator_pb2


def test_evaluate_response_which_oneof_value():
    response = evaluator_pb2.EvaluateResponse(value=2.5, duration_ms=1.0)
    assert response.WhichOneof("result") == "value"


def test_evaluate_response_which_oneof_error():
    response = evaluator_pb2.EvaluateResponse(error="boom", duration_ms=1.0)
    assert response.WhichOneof("result") == "error"


def test_evaluate_response_which_oneof_unknown_group():
    response = evaluator_pb2.EvaluateResponse(duration_ms=0.0)
    assert response.WhichOneof("result") is None
    assert response.WhichOneof("other") is None
