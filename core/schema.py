from drf_spectacular.extensions import OpenApiAuthenticationExtension


class KnoxTokenScheme(OpenApiAuthenticationExtension):
    target_class = 'knox.auth.TokenAuthentication'
    name = 'knoxTokenAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Knox token authentication. Use the header value `Token <your-token>`.',
        }
