import base64

from nacl.public import PrivateKey

from boefjes.dependencies.encryption import NaclBoxMiddleware


def test_encode_decode():
    sk = PrivateKey.generate()
    sk_b64 = base64.b64encode(bytes(sk)).decode()
    pub_b64 = base64.b64encode(bytes(sk.public_key)).decode()
    nacl_box_middleware = NaclBoxMiddleware(private_key=sk_b64, public_key=pub_b64)

    msg = "The president is taking the underpass"

    encrypted = nacl_box_middleware.encode(msg)
    decrypted = nacl_box_middleware.decode(encrypted)

    assert encrypted != msg
    assert decrypted == msg
