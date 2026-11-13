(function () {
    'use strict';

    if (!window.React || !window.ReactDOM || !window.antd) {
        return;
    }

    var rootElement = document.getElementById('react-antd-root');
    if (!rootElement) {
        return;
    }

    var React = window.React;
    var ReactDOM = window.ReactDOM;
    var antd = window.antd;

    function LegacyCrudBridge() {
        var state = React.useState(null);
        var message = state[0];
        var setMessage = state[1];

        React.useEffect(function () {
            var forms = Array.prototype.slice.call(document.querySelectorAll('form'));
            var onInvalid = function (event) {
                var form = event.currentTarget;
                var invalidFields = form.querySelectorAll(':invalid').length;
                setMessage(
                    invalidFields === 1
                        ? 'Revise o campo destacado antes de continuar.'
                        : 'Revise os ' + invalidFields + ' campos destacados antes de continuar.'
                );
            };

            forms.forEach(function (form) {
                form.addEventListener('invalid', onInvalid, true);
            });

            return function () {
                forms.forEach(function (form) {
                    form.removeEventListener('invalid', onInvalid, true);
                });
            };
        }, []);

        if (!message) {
            return null;
        }

        return React.createElement(
            antd.Alert,
            {
                type: 'warning',
                closable: true,
                showIcon: true,
                message: message,
                onClose: function () { setMessage(null); },
                style: { position: 'fixed', top: 16, right: 16, zIndex: 2000, maxWidth: 420 }
            }
        );
    }

    ReactDOM.createRoot(rootElement).render(
        React.createElement(
            antd.ConfigProvider,
            { locale: antd.locale && antd.locale.pt_BR },
            React.createElement(LegacyCrudBridge)
        )
    );
}());
