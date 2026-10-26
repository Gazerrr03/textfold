# TextFold in the browser

A button that sends the page you are reading to TextFold on this computer, as you see it: signed in, past a paywall
you pay for, drawn by the page's scripts, with what it keeps in shadow roots and frames. TextFold then reads it as it
reads any web page. Status: a first version (docs/web-capture.md); not in the Chrome Web Store yet.

## Try it (Chrome, Edge, Brave; macOS or Linux)

1. Open `chrome://extensions`, turn on **Developer mode**, choose **Load unpacked** and pick this folder.
2. Copy the extension's id from its card (32 letters).
3. Let it reach TextFold:

   ```bash
   python3 -m textfold capture install --extension <id>
   ```

   This writes the manifest of TextFold's native messaging host (`app.textfold.capture`) where each browser looks
   for it, for your user, and allows that extension alone.
4. On any page, click the TextFold button. A ✓ on it says the page is in your library; when TextFold is running, its
   reader opens beside the page. A ! says why not (hover the button).

## What it asks for

- `activeTab`: the tab you click it on, while you stay on that page. No other page is read, and none is read before
  you click.
- `scripting`: to run its own `snapshot.js` in that tab. It runs no code it did not ship with.
- `nativeMessaging`: to hand the page to TextFold through the browser. No port is opened on this computer, and only
  this extension can reach TextFold's host.

Your cookies stay in the browser: what is sent is the page as it was drawn. It goes to your library on this computer
and nowhere else.
