# pynfe/utils/nfse/speedgov/servico_cancelar_nfse_envio_v01.py
# -*- coding: utf-8 -*-
# PyXB bindings for NM:a24709013db7b86cd5a3ea1781961175ec68a2a4
# Generated 2026-11-03 15:58:19.161399 by PyXB version 1.2.6 using Python 3.13.15.final.0
# Namespace http://ws.speedgov.com.br/cancelar_nfse_envio_v1.xsd

from __future__ import unicode_literals
import pyxb
import pyxb.binding
import pyxb.binding.saxer
import io
import pyxb.utils.utility
import pyxb.utils.domutils
import sys
import pyxb.utils.six as _six
# Unique identifier for bindings created at the same time
_GenerationUID = pyxb.utils.utility.UniqueIdentifier('urn:uuid:17d90aef-898e-408c-9649-5e847fdafb00')

# Version of PyXB used to generate the bindings
_PyXBVersion = '1.2.6'

# A holder for module-level binding classes so we can access them from
# inside class definitions where property names may conflict.
_module_typeBindings = pyxb.utils.utility.Object()

# Import bindings for namespaces imported into schema
import pynfe.utils.nfse.speedgov._tipos as _ImportedBinding_pynfe_utils_nfse_speedgov__tipos
import pyxb.binding.datatypes

# NOTE: All namespace declarations are reserved within the binding
Namespace = pyxb.namespace.NamespaceForURI('http://ws.speedgov.com.br/cancelar_nfse_envio_v1.xsd', create_if_missing=True)
Namespace.configureCategories(['typeBinding', 'elementBinding'])

def CreateFromDocument (xml_text, fallback_namespace=None, location_base=None, default_namespace=None):
    """Parse the given XML and use the document element to create a
    Python instance.

    @param xml_text An XML document.  This should be data (Python 2
    str or Python 3 bytes), or a text (Python 2 unicode or Python 3
    str) in the L{pyxb._InputEncoding} encoding.

    @keyword fallback_namespace An absent L{pyxb.Namespace} instance
    to use for unqualified names when there is no default namespace in
    scope.  If unspecified or C{None}, the namespace of the module
    containing this function will be used, if it is an absent
    namespace.

    @keyword location_base: An object to be recorded as the base of all
    L{pyxb.utils.utility.Location} instances associated with events and
    objects handled by the parser.  You might pass the URI from which
    the document was obtained.

    @keyword default_namespace An alias for @c fallback_namespace used
    in PyXB 1.1.4 through 1.2.6.  It behaved like a default namespace
    only for absent namespaces.
    """

    if pyxb.XMLStyle_saxer != pyxb._XMLStyle:
        dom = pyxb.utils.domutils.StringToDOM(xml_text)
        return CreateFromDOM(dom.documentElement)
    if fallback_namespace is None:
        fallback_namespace = default_namespace
    if fallback_namespace is None:
        fallback_namespace = Namespace.fallbackNamespace()
    saxer = pyxb.binding.saxer.make_parser(fallback_namespace=fallback_namespace, location_base=location_base)
    handler = saxer.getContentHandler()
    xmld = xml_text
    if isinstance(xmld, _six.text_type):
        xmld = xmld.encode(pyxb._InputEncoding)
    saxer.parse(io.BytesIO(xmld))
    instance = handler.rootObject()
    return instance

def CreateFromDOM (node, fallback_namespace=None, default_namespace=None):
    """Create a Python instance from the given DOM node.
    The node tag must correspond to an element declaration in this module.

    @deprecated: Forcing use of DOM interface is unnecessary; use L{CreateFromDocument}."""
    if fallback_namespace is None:
        fallback_namespace = default_namespace
    if fallback_namespace is None:
        fallback_namespace = Namespace.fallbackNamespace()
    return pyxb.binding.basis.element.AnyCreateFromDOM(node, fallback_namespace)


# Complex type [anonymous] with content type ELEMENT_ONLY
class CTD_ANON (pyxb.binding.basis.complexTypeDefinition):
    """Complex type [anonymous] with content type ELEMENT_ONLY"""
    _TypeDefinition = None
    _ContentTypeTag = pyxb.binding.basis.complexTypeDefinition._CT_ELEMENT_ONLY
    _Abstract = False
    _ExpandedName = None
    _XSDLocation = pyxb.utils.utility.Location('pynfe/data/XSDs/NFS-e/Speedgov/servico_cancelar_nfse_envio_v1.xsd', 12, 2)
    _ElementMap = {}
    _AttributeMap = {}
    # Base type is pyxb.binding.datatypes.anyType
    
    # Element Pedido uses Python identifier Pedido
    __Pedido = pyxb.binding.content.ElementDeclaration(pyxb.namespace.ExpandedName(None, 'Pedido'), 'Pedido', '__httpws_speedgov_com_brcancelar_nfse_envio_v1_xsd_CTD_ANON_Pedido', False, pyxb.utils.utility.Location('pynfe/data/XSDs/NFS-e/Speedgov/servico_cancelar_nfse_envio_v1.xsd', 14, 4), )

    
    Pedido = property(__Pedido.value, __Pedido.set, None, None)

    _ElementMap.update({
        __Pedido.name() : __Pedido
    })
    _AttributeMap.update({
        
    })
_module_typeBindings.CTD_ANON = CTD_ANON


CancelarNfseEnvio = pyxb.binding.basis.element(pyxb.namespace.ExpandedName(Namespace, 'CancelarNfseEnvio'), CTD_ANON, location=pyxb.utils.utility.Location('pynfe/data/XSDs/NFS-e/Speedgov/servico_cancelar_nfse_envio_v1.xsd', 11, 1))
Namespace.addCategoryObject('elementBinding', CancelarNfseEnvio.name().localName(), CancelarNfseEnvio)



CTD_ANON._AddElement(pyxb.binding.basis.element(pyxb.namespace.ExpandedName(None, 'Pedido'), _ImportedBinding_pynfe_utils_nfse_speedgov__tipos.tcPedidoCancelamento, scope=CTD_ANON, location=pyxb.utils.utility.Location('pynfe/data/XSDs/NFS-e/Speedgov/servico_cancelar_nfse_envio_v1.xsd', 14, 4)))

def _BuildAutomaton ():
    # Remove this helper function from the namespace after it is invoked
    global _BuildAutomaton
    del _BuildAutomaton
    import pyxb.utils.fac as fac

    counters = set()
    states = []
    final_update = set()
    symbol = pyxb.binding.content.ElementUse(CTD_ANON._UseForTag(pyxb.namespace.ExpandedName(None, 'Pedido')), pyxb.utils.utility.Location('pynfe/data/XSDs/NFS-e/Speedgov/servico_cancelar_nfse_envio_v1.xsd', 14, 4))
    st_0 = fac.State(symbol, is_initial=True, final_update=final_update, is_unordered_catenation=False)
    states.append(st_0)
    transitions = []
    st_0._set_transitionSet(transitions)
    return fac.Automaton(states, counters, False, containing_state=None)
CTD_ANON._Automaton = _BuildAutomaton()

