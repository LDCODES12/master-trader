import os
import pytest
import vcr


@pytest.fixture(scope="session")
def vcr_config():
    return {
        "filter_headers": ["authorization", "X-MBX-APIKEY"],
        "record_mode": os.getenv("VCR_MODE", "once"),
        "decode_compressed_response": True,
    }


my_vcr = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    filter_headers=["authorization", "X-MBX-APIKEY"],
)


