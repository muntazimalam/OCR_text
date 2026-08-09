from app.analyzers.number_plate import NumberPlateAnalyzer


def test_valid_number_plate_detection():
    analyzer = NumberPlateAnalyzer()
    mock_ocr = {
        "text": "KA01AB1234",
        "detections": [{"text": "KA01AB1234", "confidence": 0.95}]
    }

    res = analyzer.analyze("dummy.jpg", b"", ocr_result=mock_ocr)
    assert res["detected"] is True
    assert res["valid"] is True
    assert res["plate_text"] == "KA01AB1234"
    assert res["confidence"] >= 0.90


def test_invalid_number_plate_detection():
    analyzer = NumberPlateAnalyzer()
    mock_ocr = {
        "text": "HONDA TOYOTA",
        "detections": [{"text": "HONDA", "confidence": 0.80}, {"text": "TOYOTA", "confidence": 0.80}]
    }

    res = analyzer.analyze("dummy.jpg", b"", ocr_result=mock_ocr)
    assert res["detected"] is False
    assert res["valid"] is False
    assert res["plate_text"] is None


def test_motorcycle_multiline_plate_detection():
    analyzer = NumberPlateAnalyzer()
    mock_ocr = {
        "text": "KA05 EX5678",
        "detections": [{"text": "KA05", "confidence": 0.90}, {"text": "EX5678", "confidence": 0.90}]
    }

    res = analyzer.analyze("dummy.jpg", b"", ocr_result=mock_ocr)
    assert res["detected"] is True
    assert res["valid"] is True
    assert res["plate_text"] == "KA05EX5678"


def test_international_plate_detection():
    analyzer = NumberPlateAnalyzer()
    # 7-character string should be rejected (must be exactly 10 characters)
    mock_ocr_short = {
        "text": "7ABC123",
        "detections": [{"text": "7ABC123", "confidence": 0.90}]
    }
    res_short = analyzer.analyze("dummy.jpg", b"", ocr_result=mock_ocr_short)
    assert res_short["valid"] is False
    assert res_short["detected"] is False

    # 10-character BH series plate should pass
    mock_ocr_bh = {
        "text": "22BH1234AB",
        "detections": [{"text": "22BH1234AB", "confidence": 0.90}]
    }
    res_bh = analyzer.analyze("dummy.jpg", b"", ocr_result=mock_ocr_bh)
    assert res_bh["valid"] is True
    assert res_bh["detected"] is True
    assert res_bh["plate_text"] == "22BH1234AB"
