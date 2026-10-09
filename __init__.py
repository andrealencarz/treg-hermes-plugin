"""Ponto de entrada nativo do plugin Hermes. Sem efeitos de instalação."""

if __package__:
    from .prospector.hermes_plugin import register
else:
    from prospector.hermes_plugin import register

__all__ = ["register"]
