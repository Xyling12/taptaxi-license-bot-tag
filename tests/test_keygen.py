from keygen import generate_license


def test_generate_license_is_deterministic():
    secret = "my-super-secret-key-1234567890"
    device_id = "TEST123"

    first = generate_license(device_id, secret)
    second = generate_license(device_id, secret)

    assert first == second
    assert len(first) == 16
    assert first == first.upper()


def test_generate_license_changes_for_different_device_ids():
    secret = "my-super-secret-key-1234567890"

    first = generate_license("DEVICE_A", secret)
    second = generate_license("DEVICE_B", secret)

    assert first != second
