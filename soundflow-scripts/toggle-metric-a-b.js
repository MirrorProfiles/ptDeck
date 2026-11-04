//Remember original track i was working on.
var originalTrackName = sf.ui.proTools.selectedTrackNames[0];

//Scroll to and select the track called "MASTER".
sf.ui.proTools.trackGetByName({ name: "-OUT MASTER", makeVisible: true }).track.trackScrollToView()

const pluginName = 'ADPTR MetricAB';

const group1Visible = sf.ui.proTools.getMenuItem('View', 'Edit Window Views', 'Inserts A-E').isMenuChecked;
const group2Visible = sf.ui.proTools.getMenuItem('View', 'Edit Window Views', 'Inserts F-J').isMenuChecked;
const insertButtons = sf.ui.proTools.selectedTrack.insertButtons.slice(group1Visible ? 0 : 5, group2Visible ? 10 : 5);

const eqButton = insertButtons.find(b => b.exists && b.value.invalidate().value.includes(pluginName));
if (!eqButton) throw `Could not find plugin "${pluginName}" on selected track`;

eqButton.elementClick();


var pluginWin = sf.ui.proTools.windows.whoseTitle.is('Plug-in: ADPTR MetricAB').first;
var pluginView = pluginWin.children.whoseTitle.is('FXTDMEditView').first;
if (!pluginView.exists) throw "Could not find open Audio Suite plugin view";

//Use this to log a list of all parameter names:
//log(pluginView.children.map(c => c.title.value).join('\n'));
//throw 0;

var parameterSlider = pluginView.children.whoseTitle.is('AB Switch').first;

//To select one:
/*parameterSlider.elementClick({
    actionName: 'AXIncrement'
});*/

//To select other:
/*parameterSlider.elementClick({
    actionName: 'AXDecrement'
});*/

//To toggle A/B:
if (parameterSlider.value.invalidate().intValue === 0) {
    parameterSlider.elementClick({
        actionName: 'AXIncrement'
    });
} else {
    parameterSlider.elementClick({
        actionName: 'AXDecrement'
    });
}

eqButton.elementClick();

//Scroll to and select the track i was working on.
sf.ui.proTools.trackSelectByName({ names: [originalTrackName] })
sf.ui.proTools.selectedTrack.trackScrollToView();