# acme-app-core

Screen models for the Acme mobile app. The native iOS/Android shells call
`openScreen(name, device)` and render the returned model.

    npm test                                     # unit tests
    node bin/open-screen.js settings devices/pixel-7-en-us.json   # print a screen model

Device profiles in `devices/` mirror what the shells send at startup.
