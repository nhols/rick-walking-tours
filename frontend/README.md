# Tour Player

Ultra-minimal Expo app for trying the walking-tour playback experience on a
phone.

## Run

```bash
cd frontend
npm install
npm start
```

For the quickest phone test, scan the QR code with Expo Go.

Use `npm run ios` for the iOS Simulator after Xcode is fully installed. Use
`npm run android` after Android Studio/SDK and `adb` are installed.

The app currently reads static tour bundles from per-tour directories under
`assets/tour/`:

- `<tour-id>/frontend_tour.json`
- `<tour-id>/*.wav`

The temporary tour registry lives in `availableTours.ts`, mirroring the API
shape where the app can list available tours and then retrieve files for a
specific tour.

Generated backend tour files use the same per-tour layout under
`data/tours/<tour-id>/`.
