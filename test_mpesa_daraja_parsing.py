from utils.mpesa_daraja import parse_c2b_payload, parse_stk_callback


def test_parse_stk_callback_success_extracts_receipt_and_amount():
    payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "12345",
                "CheckoutRequestID": "ws_CO_123",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 1000},
                        {"Name": "MpesaReceiptNumber", "Value": "ABCD1234"},
                        {"Name": "TransactionDate", "Value": 20260118123045},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                    ]
                },
            }
        }
    }

    parsed = parse_stk_callback(payload)
    assert parsed["result_code"] == 0
    assert parsed["checkout_request_id"] == "ws_CO_123"
    assert parsed["mpesa_receipt_number"] == "ABCD1234"
    assert parsed["amount"] == 1000
    assert parsed["phone_number"] == "254712345678"


def test_parse_c2b_payload_extracts_trans_id_and_ref():
    payload = {
        "TransactionType": "Pay Bill",
        "TransID": "QWE123XYZ",
        "TransTime": "20260118123045",
        "TransAmount": "500",
        "BusinessShortCode": "123456",
        "BillRefNumber": "INV-20260118-0001",
        "MSISDN": "254712345678",
        "FirstName": "Jane",
        "MiddleName": "",
        "LastName": "Doe",
    }

    parsed = parse_c2b_payload(payload)
    assert parsed["trans_id"] == "QWE123XYZ"
    assert parsed["bill_ref"] == "INV-20260118-0001"
    assert parsed["msisdn"] == "254712345678"
