#Author- bwees
#Description- Set Part Mass

import adsk.core, adsk.fusion, adsk.cam, traceback

commandId = 'ExportCAMConfigurations'
commandName = 'Export CAM Configurations'
commandDescription = 'Exports the selected configurations\' CAM programs to a specified folder.'

app = None
ui = None
configTable: adsk.fusion.ConfigurationTopTable = None

handlers = []

app = adsk.core.Application.get()
if app:
    ui  = app.userInterface


def getConfigurationNames():
    """
    Get the names of all configurations in the configuration table.
    """
    
    if not configTable:
        return []

    configNames = []
    for i in range(configTable.rows.count):
        configName = configTable.rows.item(i).name
        configNames.append(configName)
    return configNames

def getCAMSetups():
    """
    Get the CAM setups in the active design.
    """
    cam = adsk.cam.CAM.cast(app.activeProduct)
    if not cam:
        return []
    

    setups = []
    for setup in cam.setups:
        setups.append(setup)
    return setups

def activateConfiguration(cfgName):
    """
    Activate the configuration with the given name.
    """
    if not configTable:
        return False

    # check if the configuration exists
    cfg = configTable.rows.itemByName(cfgName)
    if not cfg:
        return False

    # activate the configuration
    cfg.activate()
    return True

def activateWorkspace(workspaceName):
    global app, ui

    """
    Activate the workspace with the given name.
    """

    app.userInterface.workspaces.itemById(workspaceName).activate()
    
    # wait for the workspace to be activated
    while app.userInterface.activeWorkspace.id != workspaceName:
        adsk.doEvents()

    # update app and ui now that the workspace is activated
    app = adsk.core.Application.get()
    ui = app.userInterface

def getCompletedFutureCount(futures: list[adsk.cam.GenerateToolpathFuture]):
    """
    Get the number of completed futures in the list.
    """
    count = 0
    for future in futures:
        if future.isGenerationCompleted:
            count += 1
    return count

def getPostProcessor(post_name: str):
    """
    Get the post processor with the given name.
    """
    cam = adsk.cam.CAM.cast(app.activeProduct)
    camManager = adsk.cam.CAMManager.get()
    libraryManager: adsk.cam.CAMLibraryManager = camManager.libraryManager
    postLibrary: adsk.cam.PostLibrary = libraryManager.postLibrary

    postQuery: adsk.cam.PostConfigurationQuery = postLibrary.createQuery(adsk.cam.LibraryLocations.Fusion360LibraryLocation)
    postQuery.vendor = "grbl"

    posts = postQuery.execute()
    return posts[0] if len(posts) > 0 else None

import adsk.core, adsk.fusion, adsk.cam, traceback

app = adsk.core.Application.get()
ui = app.userInterface

def exportSetup(setup: adsk.cam.Setup, programName: str, folder: str):
    try:
        cam = adsk.cam.CAM.cast(app.activeProduct)

        # Locate the GRBL post processor in the user library
        camManager = adsk.cam.CAMManager.get()
        postLibrary = camManager.libraryManager.postLibrary

        query = postLibrary.createQuery(adsk.cam.LibraryLocations.CloudLibraryLocation)
        query.vendor = 'Grbl'
        postConfigs = query.execute()

        if not postConfigs or len(postConfigs) == 0:
            ui.messageBox('Could not find grbl.cps in the user post library.')
            return

        postConfig = postConfigs[0]

        # Create NC Program Input
        ncInput = cam.ncPrograms.createInput()
        ncInput.displayName = programName
        ncInput.operations = [setup]

        # Output folder: temp directory
        outputFolder = folder.replace('\\', '/')
        ncInput.parameters.itemByName('nc_program_output_folder').value.value = outputFolder

        # Optional: open in editor
        ncInput.parameters.itemByName('nc_program_openInEditor').value.value = False

        # Optional: file name
        ncInput.parameters.itemByName('nc_program_filename').value.value = programName

        # Create NC program
        ncProgram = cam.ncPrograms.add(ncInput)
        ncProgram.postConfiguration = postConfig

        # Post the NC program
        postOptions = adsk.cam.NCProgramPostProcessOptions.create()
        ncProgram.postProcess(postOptions)

        # ui.messageBox(f'Exported GRBL file to:\n{outputFolder}/{programName}{postConfig.extension}')
    except:
        ui.messageBox('Error:\n{}'.format(traceback.format_exc()))


def exportMatrix(setups: list[adsk.cam.Setup], configurations: list[str], folder: str, post_name: str, name: str):
    cam = adsk.cam.CAM.cast(app.activeProduct)

    if not cam:
        print('No CAM product found')
        return
    
    progress = ui.createProgressDialog()
    progress.isCancelButtonShown = False
    progress.show('Toolpath Generation Progress', 'Generating Toolpaths', 0, len(configurations) * len(setups) * 2, True)

    totalCompleted = 0


    # for every configuration
    for cfg in configurations:
        # switch to design workspace
        activateWorkspace('FusionSolidEnvironment')

        # activate configuration
        activateConfiguration(cfg)

        # switch to CAM workspace
        activateWorkspace('CAMEnvironment')

        # generate the selected setups
        futures = []
        for setup in setups:
           futures.append(cam.generateToolpath(setup))

        # wait for generation
        while True:
            completed = getCompletedFutureCount(futures)
            if completed == len(futures):
                break
            else:
                progress.progressValue = totalCompleted + completed
                progress.message = f'Generating Toolpaths for {cfg} ({completed}/{len(futures)})'

            adsk.doEvents()


        totalCompleted += len(futures)

        # post process the selected setups
        for i, setup in enumerate(setups):
            progress.message = f'Post Processing {setup.name} for {cfg} ({i}/{len(setups)})'

            exportSetup(setup, name + '_' + cfg + "_" + setup.name, folder)

            totalCompleted += 1
            progress.progressValue = totalCompleted

    progress.hide()


    
class ExportConfigurationsCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()        
    def notify(self, args: adsk.core.CommandCreatedEventArgs):
        try:
            cmd = args.command
            cmd.isRepeatable = False
            onExecute = ExportConfigurationsHandler()
            cmd.execute.add(onExecute)
            onDestroy = ExportConfigurationsDestroyHandler()
            cmd.destroy.add(onDestroy)
            onValidateInputs = ExportConfigurationsValidateInputsHandler()
            cmd.validateInputs.add(onValidateInputs)

            handlers.append(onValidateInputs)
            handlers.append(onExecute)
            handlers.append(onDestroy)

            # Define the inputs.
            inputs = cmd.commandInputs
            
            # Create 2 tabs, one for setting the CAM export options and the other for selecting the configurations to export
            tab1 = inputs.addTabCommandInput('export', 'Export')
            tab2 = inputs.addTabCommandInput('configs', 'Configurations')
            tab1.isExpanded = True

            # Add a text input for the Project name
            projectInput = tab1.children.addStringValueInput('project_name', 'Project Name', app.activeDocument.name)
            projectInput.isPassword = False


            # Add a Radio Button Group to select the export type
            exportTypeInput = tab1.children.addDropDownCommandInput('machine', 'Machine', adsk.core.DropDownStyles.TextListDropDownStyle)
            dropDownItems = exportTypeInput.listItems
            dropDownItems.add("Starforge", True)
            dropDownItems.add("TXRX", False)

            # add a divider
            tab1.children.addSeparatorCommandInput('sep1')



            # Show table with checkboxes and names of CAM Programs
            for setup in getCAMSetups():
                # add a checkbox for each setup
                checkBoxInput = tab1.children.addBoolValueInput("export_" + setup.name, setup.name, True, "", True)


            # Show table with checkboxes and names of configurations
            for cfg in getConfigurationNames():
                cfg_id = cfg.replace(" ", "_").replace(".", "_")
                # add a checkbox for each configuration
                checkBoxInput = tab2.children.addBoolValueInput("export_" + cfg_id, cfg, True, "", True)

            # change the "OK button" to "Export"
            cmd.okButtonText = 'Export'


        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


class ExportConfigurationsHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # get destination folder
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = app.activeProduct
            if not design:
                ui.messageBox('No active design')
                return
            
            ## Open folder dialog
            folderDlg = ui.createFolderDialog()
            folderDlg.title = 'Select Folder to Export'

            dlgResult = folderDlg.showDialog()
            if dlgResult == adsk.core.DialogResults.DialogOK:
                selectedFolder = folderDlg.folder
                # ui.messageBox(f'Selected folder:\n{selectedFolder}')

                # Use selectedFolder for exporting files
                selectedSetups = []
                selectedConfigurations = []

                # get the selected setups
                for setup in getCAMSetups():
                    # get the checkbox input
                    checkBoxInput = args.command.commandInputs.itemById("export_" + setup.name)
                    if checkBoxInput:
                        if checkBoxInput.value:
                            selectedSetups.append(setup)

                # get the selected setups
                for cfg in getConfigurationNames():
                    cfg_id = cfg.replace(" ", "_").replace(".", "_")

                    # get the checkbox input
                    checkBoxInput = args.command.commandInputs.itemById("export_" + cfg_id)
                    if checkBoxInput:
                        if checkBoxInput.value:
                            selectedConfigurations.append(cfg)


                projetNameInput = args.command.commandInputs.itemById('project_name')
                projectName = projetNameInput.value

                exportMatrix(getCAMSetups(), getConfigurationNames(), selectedFolder, "Starforge", projectName)


        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

class ExportConfigurationsValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        eventArgs = adsk.core.ValidateInputsEventArgs.cast(args)

        cfgCount = 0
        for cfg in getConfigurationNames():
            # get the checkbox input
            cfg_id = cfg.replace(" ", "_").replace(".", "_")
            checkBoxInput = eventArgs.inputs.itemById("export_" + cfg_id)
            if checkBoxInput:
                if checkBoxInput.value:
                    cfgCount += 1

        setupCount = 0
        for setup in getCAMSetups():
            # get the checkbox input
            checkBoxInput = eventArgs.inputs.itemById("export_" + setup.name)
            if checkBoxInput:
                if checkBoxInput.value:
                    setupCount += 1

        # if no checkboxes are checked, disable the OK button
        if cfgCount == 0 or setupCount == 0:
            eventArgs.areInputsValid = False
        else:
            eventArgs.areInputsValid = True

class ExportConfigurationsDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


def run(context):
    global configTable

    try:
        # get all configurations in the active design
        design = app.activeProduct
        if not design:
            ui.messageBox('No active design')
            return

        # capture the configuration table
        activateWorkspace('FusionSolidEnvironment')
        configTable = app.activeProduct.configurationTopTable

        if len(getConfigurationNames()) == 0:
            ui.messageBox('No configuration table found. Make sure the design is a multi-configuration design.')
            return


        activateWorkspace('CAMEnvironment')
        if len(getCAMSetups()) == 0:
            ui.messageBox('No CAM setups found. Make sure the design has CAM setups.')
            return
        
        
        cmdDef = ui.commandDefinitions.itemById(commandId)
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition(commandId, commandName, commandDescription) # no resource folder is specified, the default one will be used

        onCommandCreated = ExportConfigurationsCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        
        # keep the handler referenced beyond this function
        handlers.append(onCommandCreated)

        inputs = adsk.core.NamedValues.create()
        cmdDef.execute(inputs)

        # prevent this module from being terminate when the script returns, because we are waiting for event handlers to fire
        adsk.autoTerminate(False)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
