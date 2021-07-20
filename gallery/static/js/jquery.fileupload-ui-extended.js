(function ($, window, document, undefined) {
    'use strict';

    $.fn.dataCollection = function () {
        var data = {};
        [].forEach.call(this.get(0).attributes, function (attr) {
            if (/^data-/.test(attr.name)) {
                var name = attr.name.substr(5);
                data[name] = attr.value;
            }
        });
        return data;
    };

    $.blueimp.fileupload.prototype._specialOptions.push(
        'mediaUrl',
        'hiddenFileInput',
        'hiddenDeletedInput',
        'deletedTemplateId',
        'deletedFilesContainer',
        'editModalId',
        'editModalImgId',
        'sortableHandleSelector',
        'sortableOptions',
        'cropperResultMessageBoxSelector',
        'cropperButtonDivSelector',
        'cropperButtonSelector',
        'statusDataName',
        'filesDataToInputDataFunction',
        'is_initializing',
    );

    $.widget(
        'blueimp.fileupload', $.blueimp.fileupload, {

            options: {
                hiddenFileInput: undefined,
                hiddenDeletedInput: undefined,
                mediaUrl: undefined,
                editModalId: undefined,
                editModalImgId: undefined,
                cropperResultMessageBoxSelector: undefined,
                cropperButtonDivSelector: undefined,
                cropperStatusBtnSelector: undefined,
                cropperRotateBtnSelector: undefined,
                enableSortable: true,
                sortableHandleSelector: undefined,
                sortableOptions:undefined,
                statusDataName: undefined,
                deletedTemplateId: "template-deleted",
                deletedFilesContainer: undefined,

                getNumberOfUploadedFiles: function () {
                    return this.filesContainer.children('.template-download')
                        .not('.processing').length;
                },

                getFilesDataFromDataContext: function (data) {
                    if (!data.context) return [];
                    var file = data.context.find('.preview').dataCollection();
                    if (! file) return [];
                    return file;
                },

                added: function (e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }

                    var $this = $(this),
                        that = $this.data('blueimp-fileupload') ||
                            $this.data('fileupload');

                    that._trigger("before_submit", e, data);

                    if (!data.files) return false;
                    if (data.replaceChild && data.replaceChild.length){
                        if (that._trigger('replace', e, data) !== false)
                        {delete data.replaceChild;}
                    }
                    $(data.context).find('.edit').prop('disabled', false);
                    that.toggleFileuploadSortableHandle();
                    that._toggleFileuploadButtonBarButtonDisplay();
                },

                replace: function (e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }
                    var $this = $(this),
                        that = $this.data('blueimp-fileupload') ||
                            $this.data('fileupload');
                    $(data.context).replaceAll(data.replaceChild);
                    that._trigger('replaced', e, data);
                },

                failed: function(e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }
                    $(data.context).find('.edit').prop('disabled', false).addClass("hidden").end();

                    var that = $(this).data('blueimp-fileupload') || $(this).data('fileupload');
                    that.toggleFileuploadSortableHandle()
                        ._toggleFileuploadButtonBarButtonDisplay()._toggleFileuploadButtonBarDelete();
                },

                completed: function (e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }
                    var that = $(this).data('blueimp-fileupload') || $(this).data('fileupload');
                    that.toggleFileuploadSortableHandle()
                        ._toggleFileuploadButtonBarButtonDisplay()._toggleFileuploadButtonBarDelete();
                    that._trigger("post_completed", e, data);
                    that._fillInHiddenInputs(data);
                },

                destroyed: function (e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }
                    var that = $(this).data('blueimp-fileupload') ||
                            $(this).data('fileupload'),
                        files,
                        template, deferred;

                    files = [that.options.getFilesDataFromDataContext(data)];

                    if(files){
                        template = that._renderDeleted(files).appendTo(that.options.deletedFilesContainer);
                        that._forceReflow(template);
                        deferred = that._addFinishedDeferreds();
                        that._transition(template).done(
                            function () {
                                data.context = $(this);
                                that._trigger('completed', e, data);
                                that._trigger('finished', e, data);
                                that._trigger('post-destroy', e, data);
                                deferred.resolve();
                            }
                        );
                    }

                    that.toggleFileuploadSortableHandle()
                        ._toggleFileuploadButtonBarButtonDisplay()._toggleFileuploadButtonBarDelete();
                },

                // fixme: bug when undelete
                undelete: function (e, data) {
                    if (e.isDefaultPrevented()) {
                        return false;
                    }

                    var that = $(this).data('blueimp-fileupload') ||
                            $(this).data('fileupload'),
                        files = [that.options.getFilesDataFromDataContext(data)],
                        removeNode = function () {
                            that._transition(data.context).done(
                                function () {
                                    $(this).remove();
                                        that._trigger('done', e, {
                                            "result": {
                                                "success": "true",
                                                "files": files
                                            }});
                                });
                        };
                    removeNode();
                    data.context = $(this);
                    that._trigger('completed', e, data);
                    that._trigger('finished', e, data);
                    that._trigger('post-destroy', e, data);
                },

                sortableUpdate: function (e, data) {
                    var that = $(this).data('blueimp-fileupload') ||
                            $(this).data('fileupload');
                    data.context = $(this);
                    that._trigger('completed', e, data);
                    that._trigger('finished', e, data);
                },
            },

            _fillIn: function (input, files) {
                var input_data = files.length ? JSON.stringify(files) : "";
                input.val(this.options.filesDataToInputDataFunction(input_data));
                if (input.hasClass("initializing")){
                    // prevent initialization from trigger inputChanged events.
                    input.removeClass("initializing")
                } else {
                    this._trigger("inputChanged");
                }
            },
            _fillInHiddenInputs: function (data) {
                var filesInput = this.options.hiddenFileInput,
                    deletedInput = this.options.hiddenDeletedInput,
                    files_data = [], deleted_data = [];

                // get input files_data
                this.options.filesContainer.children('.template-download')
                        .not('.processing').find('.preview').each(function () {
                            files_data.push($(this).dataCollection());
                        });

                this._fillIn(filesInput, files_data);

                // get deleted files_data
                this.options.deletedFilesContainer
                    .children('.template-deleted')
                    .not('.processing')
                    .find('.preview')
                    .each(function () {
                            deleted_data.push($(this).dataCollection());
                        });
                this._fillIn(deletedInput, deleted_data);

                },

            _initEventHandlers: function () {
                this._super();
                var filesContainer = this.options.filesContainer,
                    deletedFilesContainer = this.options.deletedFilesContainer;
                this._on(filesContainer, {
                    'click .edit': this._editHandler
                });
                this._on(deletedFilesContainer, {
                    'click .undelete': this._undeleteHandler
                });
                this._on(this.element, {
                    'change .toggle': this._toggleFileuploadButtonBarDeleteDisable
                });
            },

            _undeleteHandler: function (e) {
                e.preventDefault();
                var button = $(e.currentTarget);
                this._trigger('undelete', e, $.extend({
                    context: button.closest('.template-deleted'),
                }, button.data()));
            },

            _toggleFileuploadButtonBarDeleteDisable: function(e) {
                this.element.find('.fileupload-buttonbar')
                    .find('.delete')
                    .prop(
                        'disabled',
                        !(this.element.find('.toggle').is(':checked'))
                    );
            },

            toggleFileuploadSortableHandle: function() {
                var $this = $(this),
                    options = this.options;
                if (!options.enableSortable) return;

                var filesContainer = options.filesContainer;
                if (filesContainer.children().length > 1) {
                    filesContainer.find(options.sortableHandleSelector).removeClass("hidden").end();
                } else {
                    filesContainer.find(options.sortableHandleSelector).addClass("hidden").end();
                }
                return this;
            },

            _toggleFileuploadButtonBarButtonDisplay: function() {
                var filesContainer = this.options.filesContainer,
                    bool = filesContainer.find('.template-upload').length === 0;
                this.element.find('.fileupload-buttonbar')
                    .find('.start, .cancel')
                    .css("display", bool ? "none" : "")
                    .prop("disabled", bool)
                    .end();
                return this;
            },

            _toggleFileuploadButtonBarDelete: function () {
                var filesContainer = this.options.filesContainer;
                var that = this.element,
                    disabledBool = that.find(".toggle:checked").length === 0,
                    displayBool = !(this.options.getNumberOfUploadedFiles());
                that.find('.fileupload-buttonbar')
                    .find('.delete')
                    .css("display", displayBool ? "none" : "").prop("disabled", disabledBool).end()
                    .find(".toggle")
                    .css("display", displayBool ? "none" : "")
                    .end();
                return this;
            },

            _editHandler: function (e) {
                e.preventDefault();

                var $button = $(e.currentTarget),
                    options = this.options,
                    $fileupload = this.element,
                    template = $button.closest('.template-upload,.template-download'),
                    editType = template.hasClass("template-download") ? "download" : "upload",
                    $editModal = options.editModalId,
                    $editImg = options.editModalImgId;

                if (editType === "upload") {
                    var data = template.data("data");
                    if (!data) {
                        $button.prop("disabled", true);
                        return;
                    }
                    var orig, mod = data.files[0];
                    $.each(data.originalFiles, function (i, v) {
                        if (v.name === mod.name) {
                            orig = v;
                            return true;
                        }
                    });
                    if (!orig) {
                        return;
                    }

                    $editImg.prop('src', loadImage.createObjectURL(orig));
                    $editImg.processCroppedCanvas = function (result) {
                        $editModal.modal('hide');
                        options.cropperButtonSelector.prop("disabled", true);
                        template.find(".btn").prop("disabled", true);

                        // cheat maxNumberOfFiles count minus 1
                        data.context.addClass('processing');
                        result.toBlob(function (blob) {
                            blob.name = mod.name;
                            $fileupload.fileupload(
                                'add', {
                                    files: [blob],
                                    replaceChild: $(data.context)
                                }
                            );
                        }, orig.type);
                    };
                }

                if (editType === "download") {
                    $editImg.attr('src', $button.data("src"));
                    $editImg.submitData = function (result) {
                        var messageBox = options.cropperResultMessageBoxSelector;
                        options.cropperButtonSelector.prop("disabled", true);
                        $editImg.cropper('disable');
                        var jqxhr = $.ajax({
                            method: "POST",
                            url: $button.data("action"),
                            data: {"croppedResult": JSON.stringify(result)},
                            beforeSend: function (xhr, settings) {
                                xhr.setRequestHeader("X-CSRFToken", $button.data("data"));
                            }
                        })
                            .always(function () {
                            })
                            .done(function (response) {
                                options.done.call($fileupload,
                                    $.Event('done'),
                                    {
                                        result: {files: [response.file]},
                                        context: $button.closest(".template-download")
                                    });
                                messageBox.html("<span class='alert alert-success'>" + response.message +"</span>");
                                $editModal.data("new", false);
                                    setTimeout(function () {
                                        if(!$editModal.data("new")){$editModal.modal('hide')}
                                    }, 3000);
                            })
                            .fail(function (response) {
                                messageBox.html("<span class='alert alert-danger'>" + response.responseJSON.message + "</span>");
                            });
                        return false;
                    };
                }

                $editImg.rotateCanvas = function () {
                    var $this = $(this);
                    var contData = $this.cropper('getContainerData');
                    var canvData = $this.cropper('getCanvasData');
                    var newWidth = canvData.width * (contData.height / canvData.height);

                    if (newWidth >= contData.width) {
                        var newHeight = canvData.height * (contData.width / canvData.width);
                        var newCanvData = {
                            height: newHeight,
                            width: contData.width,
                            top: (contData.height - newHeight) / 2,
                            left: 0
                        };
                    } else {
                        newCanvData = {
                            height: contData.height,
                            width: newWidth,
                            top: 0,
                            left: (contData.width - newWidth) / 2
                        };
                    }
                    $this.cropper('setCanvasData', newCanvData).cropper('setCropBoxData', newCanvData);
                    options.cropperButtonSelector.prop("disabled", false);
                };

                $editModal.modal('show', [$editImg, editType]);
            },

            _initEditModalId: function () {
                var options = this.options;
                if (options.editModalId === undefined) {
                    options.editModalId = this.element.find(".edit-modal");
                } else if (!(options.editModalId instanceof $)) {
                    options.editModalId = $(options.editModalId);
                }
            },

            _initEditModalImgId: function () {
                var options = this.options;
                if (options.editModalImgId === undefined) {
                    options.editModalImgId = this.element.find(".modal-image");
                } else if (!(options.editModalImgId instanceof $)) {
                    options.editModalImgId = $(options.editModalImgId);
                }
            },

            _initCropperResultMessageBoxSelector: function () {
                var options = this.options;
                if (options.cropperResultMessageBoxSelector === undefined) {
                    options.cropperResultMessageBoxSelector = this.element.find(".cropper-message");
                } else if (!(options.cropperResultMessageBoxSelector instanceof $)) {
                    options.cropperResultMessageBoxSelector = $(options.cropperResultMessageBoxSelector);
                }
            },

            _initCropperButtonDivSelector: function () {
                var options = this.options;
                if (options.cropperButtonDivSelector === undefined) {
                    options.cropperButtonDivSelector = this.element.find(".cropper-btns");
                } else if (!(options.cropperButtonDivSelector instanceof $)) {
                    options.cropperButtonDivSelector = $(options.cropperButtonDivSelector);
                }
            },

            _initCropperButtonSelector: function () {
                var options = this.options;
                options.cropperButtonSelector = options.cropperButtonDivSelector.find(".btn")
            },

            _initCropperStatusBtnSelector: function () {
                var options = this.options;
                if (options.cropperStatusBtnSelector === undefined) {
                    options.cropperStatusBtnSelector = this.element.find('.cropper-status-btns .btn');
                } else if (!(options.cropperStatusBtnSelector instanceof $)) {
                    options.cropperStatusBtnSelector = $(options.cropperStatusBtnSelector);
                }
            },

            _initCropperRotateBtnSelector: function () {
                var options = this.options;
                if (options.cropperRotateBtnSelector === undefined) {
                    options.cropperRotateBtnSelector = this.element.find(".cropper-rotate-btns .btn");
                } else if (!(options.cropperRotateBtnSelector instanceof $)) {
                    options.cropperRotateBtnSelector = $(options.cropperRotateBtnSelector);
                }
            },

            _initEditModalEventHandler: function(){
                var $editModal = this.options.editModalId,
                    that = this,
                    options = that.options,
                    $image, editType, croppStartingData;
                $editModal.on('show.bs.modal', function (e) {
                    $image = e.relatedTarget[0];
                    editType = e.relatedTarget[1];
                })
                    .on('shown.bs.modal', function () {
                        $(this).data('new', true);
                        that._trigger("modalshownevent", event, true);
                        $image.cropper({
                            viewMode: 1,
                            checkOrientation: false,
                            autoCrop: true,
                            autoCropArea: 1,
                            strict: true,
                            movable: false,
                            zoomable: false,
                            minContainerheight: $(window).height() * 0.8,
                            ready: function (e) {
                                croppStartingData = $image.cropper("getData", "true");
                                options.cropperRotateBtnSelector.prop("disabled", false);
                            },
                            cropstart: function (e) {
                                that._trigger('modalinprogessstatus', event, true);
                            },
                            crop: function (e) {
                            },
                            cropend: function (e) {
                                var currentData = $image.cropper("getData", "true");
                                var cropNotChanged = JSON.stringify(croppStartingData) === JSON.stringify(currentData);
                                options.cropperStatusBtnSelector.prop("disabled", cropNotChanged);
                                that._trigger('modalinprogessstatus', event, !cropNotChanged);
                            }
                        });

                    })
                    .on('hidden.bs.modal', function () {
                        that._trigger('modalinprogessstatus', event, false);
                        that._trigger("modalhiddenevent", event, true);
                        $image.cropper('destroy');
                        $(this).attr("data-new", false);
                        options.cropperButtonSelector
                            .prop("disabled", true);
                        options.cropperResultMessageBoxSelector
                            .empty()
                            .end()
                            .active = false;
                    })
                    .on('show.bs.modal', function (e) {
                        that._trigger("modalshowevent", event, true);
                    })
                    .on('hide.bs.modal', function (e) {
                        that._trigger("modalhideevent", event, true);
                    });

                options.cropperButtonDivSelector.on(
                    'click',
                    '[data-method]',
                    function () {
                        var data = $.extend({}, $(this).data()); // Clone
                        if (data.method === "rotate") {
                            var contData = $image.cropper('getContainerData');
                            $image.cropper('setCropBoxData', {
                                width: 2,
                                height: 2,
                                top: (contData.height / 2) - 1,
                                left: (contData.width / 2) - 1
                            });
                            contData = null;
                        }
                        else if (data.method === "commit") {
                            if (editType === "download") {
                                data.method = "getData";
                                data.option = "true";
                            }
                            else if (editType === "upload") {
                                data.method = "getCroppedCanvas";
                            }
                        }

                        that._trigger('modalinprogessstatus', event, true);

                        var result = $image.cropper(data.method, data.option,
                            data.secondOption);

                        switch (data.method) {
                            case 'scaleX':
                            case 'scaleY':
                                $(this).data('option', -data.option);
                                break;
                            case 'reset':
                                options.cropperStatusBtnSelector.prop("disabled", true);
                                break;
                            case 'getData':
                                if (result && $image.submitData) {
                                    $image.submitData(result);
                                }
                                break;
                            case 'getCroppedCanvas':
                                if (result && $image.processCroppedCanvas) {
                                    $image.processCroppedCanvas(result);
                                }
                                break;
                            case 'rotate':
                                if (result && $image.rotateCanvas) {
                                    $image.rotateCanvas();
                                }
                                break;
                        }

                        var currentData = $image.cropper("getData", "true");

                        if (JSON.stringify(croppStartingData) === JSON.stringify(currentData))
                        {options.cropperStatusBtnSelector.prop("disabled", true);
                        that._trigger('modalinprogessstatus', event, false);}

                    });
            },

            _initEditModal: function(){
                this._initEditModalId();
                this._initEditModalImgId();
                this._initCropperResultMessageBoxSelector();
                this._initCropperButtonDivSelector();
                this._initCropperButtonSelector();
                this._initCropperStatusBtnSelector();
                this._initCropperRotateBtnSelector();
                this._initEditModalEventHandler();
            },

           _initStatusDataName: function () {
                var options = this.options;
                if (options.statusDataName === undefined) {
                    options.statusDataName = "file-pk";
                }
            },

            _initSortableHandleSelector: function () {
                var options = this.options;
                if (options.sortableHandleSelector === undefined) {
                    options.sortableHandleSelector = ".sortableHandle";
                } else if (options.sortableHandleSelector instanceof $) {
                    options.sortableHandleSelector = options.sortableHandleSelector.selector;
                }
            },

            _initSortable: function() {
                this._initSortableHandleSelector();
                var options = this.options,
                    sortableOptions = options.sortableOptions,
                    that = this,
                    defaultSortableOptions = {
                        delay: 500,
                        scrollSpeed: 40,
                        handle: options.sortableHandleSelector,
                        helper: "clone",
                        axis: "y",
                        opacity: 0.9,
                        cursor: "move",
                        start: function(e, ui){
                            that._trigger("sortableStart", e, ui.item);
                            },
                        stop: function(e, ui){
                            that._trigger("sortableStop", e, ui.item);
                        },
                        update: function(e, ui){
                            that._trigger("sortableUpdate", e, ui.item);
                        }
                    };
                if (sortableOptions) {
                    delete sortableOptions.handle;
                    sortableOptions = $.extend(defaultSortableOptions, sortableOptions);
                }
                else{
                    sortableOptions = defaultSortableOptions;
                }

                this.options.filesContainer.sortable(
                    sortableOptions
                ).disableSelection();
            },

            _initFilesDataToInputDataFunction: function () {
                var options = this.options;
                if (options.filesDataToInputDataFunction === undefined) {
                    options.filesDataToInputDataFunction = function(filesData) {return filesData};
                }
            },

            _initSpecialOptions: function () {
                this._initDeletedFilesContainer();
                this._super();
                this._initStatusDataName();
                this._initSortable();
                this._initEditModal();
                this._initWidgetHiddenInput();
                this._initFilesDataToInputDataFunction();
            },

            _initTemplates: function () {
                this._super();
                var options = this.options;
                options.templatesContainer = this.document[0].createElement(
                    options.deletedFilesContainer.prop('nodeName')
                );

                if (tmpl) {
                    if (options.deletedTemplateId) {
                        options.deletedTemplate = tmpl(options.deletedTemplateId);
                    }
                }
            },
            _renderDeleted: function (files) {
                return this._renderTemplate(
                    this.options.deletedTemplate,
                    files
                );
            },
            _initDeletedFilesContainer: function () {
                var options = this.options;
                if (options.deletedFilesContainer === undefined) {
                    options.deletedFilesContainer = this.element.find('.deleted-file');
                } else if (!(options.deletedFilesContainer instanceof $)) {
                    options.deletedFilesContainer = $(options.deletedFilesContainer);
                }
            },
            _initWidgetHiddenInput: function () {
                var options = this.options;
                if (options.hiddenFileInput === undefined) {
                    options.hiddenFileInput = this.element.find("input[id$='_0'][name$='_0']");
                } else if (!(options.hiddenFileInput instanceof $)) {
                    options.hiddenFileInput = $(options.hiddenFileInput);
                }
                if (options.hiddenDeletedInput === undefined) {
                    options.hiddenDeletedInput = this.element.find("input[id$='_1'][name$='_1']");
                } else if (!(options.hiddenDeletedInput instanceof $)) {
                    options.hiddenDeletedInput = $(options.hiddenDeletedInput);
                }
            },
        }
    );
})(jQuery, window, document);