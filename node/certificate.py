from OpenSSL import crypto
import os

def generate_ca_certificate():
    """Generate a CA certificate"""
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()
    cert.get_subject().CN = "Marzban CA"
    cert.get_subject().O = "Marzban"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(100*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.add_extensions([
        crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
        crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
        crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
    ])
    cert.sign(k, 'sha512')
    return {
        "cert": crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"),
        "key": crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")
    }

def generate_certificate(ca_cert_pem=None, ca_key_pem=None):
    """Generate a certificate signed by the CA"""
    if not ca_cert_pem or not ca_key_pem:
        # Generate self-signed certificate if no CA provided
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)
        cert = crypto.X509()
        cert.get_subject().CN = "Gozargah"
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(100*365*24*60*60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha512')
    else:
        # Generate certificate signed by CA
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)
        cert = crypto.X509()
        cert.get_subject().CN = "Marzban Node"
        cert.get_subject().O = "Marzban"
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(100*365*24*60*60)

        # Load CA certificate and key
        ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_cert_pem)
        ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, ca_key_pem)

        cert.set_issuer(ca_cert.get_subject())
        cert.set_pubkey(k)
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
            crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyEncipherment"),
            crypto.X509Extension(b"extendedKeyUsage", True, b"serverAuth, clientAuth"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        ])
        cert.sign(ca_key, 'sha512')

    return {
        "cert": crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"),
        "key": crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")
    }