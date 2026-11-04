var menuSuffix = sf.ui.proTools.hasMenuItem('File', 'Save Session') ? ' Session' : '';

// First save the current version
sf.ui.proTools.getMenuItem('File', 'Save' + menuSuffix).elementClick({}, function () { }); // Can be disabled

// Get our filename without extension
var fileNameWithoutExtension = sf.ui.proTools.mainWindow.invalidate().sessionPath.split('/').slice(-1)[0].split('.').slice(0, -1).join('.');

// Create a new name (get the name and suffixed number - if your session name was 'My Session 42' then save 'My Session ' in grps[1] and '42' in grps[2])
var grps = fileNameWithoutExtension.match(/^(.*?\.)(\d+)(.*?)$/);

// Construct a new name based on the prefix and the number (+1), followed by any suffix. If there was no number, just add '.01'
var newNumber = !grps || grps.length === 0 || isNaN(Number(grps[2])) ? '01' : (Number(grps[2]) + 1).toString().padStart(2, '0');
var newName = (grps ? grps[1] : (fileNameWithoutExtension + '.')) + newNumber + (grps ? grps[3] : '') + '.ptx';

// Invoke File Save As.
sf.ui.proTools.getMenuItem('File', `Save${menuSuffix} As...`).elementClick();

// Wait for the Save dialog to appear
var dlg = sf.ui.proTools.windows.invalidate().whoseTitle.is('Save').first.elementWaitFor().element;

// Enter the new name
dlg.textFields.first.value.value = newName;

// Add a short delay
sf.wait({ intervalMs: 500 });

// Click Save
sf.ui.proTools.windows.whoseTitle.is("Save").first.buttons.whoseTitle.is("Save").first.elementClick();
