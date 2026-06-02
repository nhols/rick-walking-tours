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

The app currently reads a static tour bundle from `assets/tour/`:

- `frontend_tour.json`
- one `.wav` file per stop
