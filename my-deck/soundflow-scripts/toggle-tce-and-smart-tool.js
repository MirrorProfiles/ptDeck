sf.ui.proTools.appActivateMainWindow();

if (sf.ui.proTools.mainWindow.cursorToolCluster.trimTool.title.invalidate().value.indexOf('Time Compression') < 0) {
    sf.ui.proTools.mainWindow.cursorToolCluster.trimTool.popupMenuSelect({ menuPath: ['TCE'], isRightClick: true });
} else {
    sf.ui.proTools.mainWindow.cursorToolCluster.trimTool.popupMenuSelect({ menuPath: ['Standard'], isRightClick: true });
}

sf.ui.proTools.toolsSelect({
    tool: 'Smart'
});