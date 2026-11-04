
sf.app.launch({
    path: "/System/Applications/QuickTime Player.app",
});

sf.wait();

sf.ui.app('com.apple.QuickTimePlayerX').menuClick({
    menuPath: ["File","New Audio Recording"],
});

sf.wait({
    intervalMs: 1500,
});

sf.ui.app("com.apple.QuickTimePlayerX").mainWindow.buttons.whoseDescription.is("show capture device selection pop up").first.popupMenuSelect({
    menuPath: ["Pro Tools Audio Bridge 2-A"],
});

