from bits.definitions import BitDefinition, BitParameterDefinition
from octopoes.models.ooi.certificate import TLSCertificateChain, X509CertificateV2

BIT = BitDefinition(
    id="expiring-certificate",
    consumes=X509CertificateV2,
    parameters=[
        # Chains that present this certificate: a presentation binds the
        # certificate to an endpoint (exactly one of IPService or
        # HostnameIPService is its key). Without a presentation — a
        # certificate known only from the transparency logs — there is no
        # endpoint whose renewal is due, and nothing is assessed.
        BitParameterDefinition(ooi_type=TLSCertificateChain, relation_path="presented_certificates")
    ],
    module="bits.expiring_certificate.expiring_certificate",
    min_scan_level=0,
)
