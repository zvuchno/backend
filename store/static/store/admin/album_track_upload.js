(function () {
    'use strict';

    const STORAGE_RETRY_DELAYS = [1000];
    const COMPLETE_RETRY_DELAYS = [1000, 2000, 4000];

    class UploadRequestError extends Error {
        constructor(message, status = null) {
            super(message);
            this.name = 'UploadRequestError';
            this.status = status;
        }
    }

    class UploadFlowError extends Error {
        constructor({ cause, stage, uploadData = null }) {
            super(cause.message);
            this.name = 'UploadFlowError';
            this.cause = cause;
            this.stage = stage;
            this.uploadData = uploadData;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const root = document.querySelector('[data-track-upload]');

        if (!root) {
            return;
        }

        const input = root.querySelector('#id_track_upload_file');
        const submitButton = root.querySelector(
            '[data-track-upload-submit]',
        );
        const retryButton = root.querySelector(
            '[data-track-upload-retry]',
        );
        const statusElement = root.querySelector(
            '[data-track-upload-status]',
        );
        const uploadList = root.querySelector(
            '[data-track-upload-list]',
        );
        const initiateUrl = root.dataset.initiateUrl;

        let activeFiles = [];
        let queueItems = [];
        let failedContext = null;

        function setStatus(message, isError = false) {
            statusElement.textContent = message;
            statusElement.classList.toggle('errornote', isError);
        }

        function setLoading(isLoading) {
            submitButton.disabled = isLoading;
            input.disabled = isLoading;

            if (retryButton) {
                retryButton.disabled = isLoading;
            }
        }

        function showRetryButton(show) {
            if (!retryButton) {
                return;
            }

            retryButton.hidden = !show;
        }

        function getCsrfToken() {
            const cookiePrefix = 'csrftoken=';
            const cookies = document.cookie.split(';');

            for (const rawCookie of cookies) {
                const cookie = rawCookie.trim();

                if (cookie.startsWith(cookiePrefix)) {
                    return decodeURIComponent(
                        cookie.slice(cookiePrefix.length),
                    );
                }
            }

            return '';
        }

        function wait(milliseconds) {
            return new Promise((resolve) => {
                window.setTimeout(resolve, milliseconds);
            });
        }

        function getFileLabel(file, index, total) {
            return `${index + 1}/${total} — ${file.name}`;
        }

        function createQueue(files) {
            uploadList.replaceChildren();

            return files.map((file, index) => {
                const item = document.createElement('li');

                item.textContent = `${getFileLabel(
                    file,
                    index,
                    files.length,
                )} — ожидает загрузки`;

                uploadList.append(item);

                return item;
            });
        }

        function setQueueItemStatus(item, message, state = 'pending') {
            item.textContent = message;

            item.classList.remove(
                'track-upload-pending',
                'track-upload-progress',
                'track-upload-success',
                'track-upload-error',
            );

            item.classList.add(`track-upload-${state}`);
        }

        function isRetryableError(error) {
            return (
                error instanceof UploadRequestError
                && (
                    error.status === null
                    || error.status >= 500
                )
            );
        }

        async function getErrorMessage(response, fallbackMessage) {
            try {
                const payload = await response.json();
                const detail = payload.detail;

                if (Array.isArray(detail)) {
                    return detail.join(' ');
                }

                if (detail) {
                    return detail;
                }
            } catch {
                // Object Storage может вернуть XML или пустое тело.
            }

            return fallbackMessage;
        }

        async function initiateUpload(file) {
            let response;

            try {
                response = await fetch(initiateUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({
                        filename: file.name,
                        size: file.size,
                        content_type: file.type,
                    }),
                });
            } catch {
                throw new UploadRequestError(
                    'Не удалось подготовить загрузку трека.',
                );
            }

            if (!response.ok) {
                throw new UploadRequestError(
                    await getErrorMessage(
                        response,
                        'Не удалось подготовить загрузку трека.',
                    ),
                    response.status,
                );
            }

            return response.json();
        }

        async function uploadFile(file, transport) {
            const formData = new FormData();

            for (const [name, value] of Object.entries(
                transport.fields,
            )) {
                formData.append(name, value);
            }

            formData.append(
                transport.file_field_name,
                file,
            );

            let response;

            try {
                response = await fetch(transport.url, {
                    method: transport.method,
                    headers: transport.headers,
                    body: formData,
                });
            } catch {
                throw new UploadRequestError(
                    'Не удалось передать файл в хранилище.',
                );
            }

            if (!response.ok) {
                throw new UploadRequestError(
                    await getErrorMessage(
                        response,
                        'Не удалось передать файл в хранилище.',
                    ),
                    response.status,
                );
            }
        }

        async function completeUpload(completeUrl) {
            let response;

            try {
                response = await fetch(completeUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    },
                });
            } catch {
                throw new UploadRequestError(
                    'Не удалось подтвердить загрузку трека.',
                );
            }

            if (!response.ok) {
                throw new UploadRequestError(
                    await getErrorMessage(
                        response,
                        'Не удалось подтвердить загрузку трека.',
                    ),
                    response.status,
                );
            }

            return response.json();
        }

        async function runWithRetry(
            operation,
            retryDelays,
            onRetry,
        ) {
            for (
                let attempt = 0;
                attempt <= retryDelays.length;
                attempt += 1
            ) {
                try {
                    return await operation();
                } catch (error) {
                    const isLastAttempt = (
                        attempt === retryDelays.length
                    );

                    if (
                        !isRetryableError(error)
                        || isLastAttempt
                    ) {
                        throw error;
                    }

                    const delay = retryDelays[attempt];

                    onRetry(delay, attempt + 1);
                    await wait(delay);
                }
            }

            throw new Error('Не удалось выполнить загрузку.');
        }

        async function processFile({
            file,
            index,
            queueItem,
            uploadData = null,
            resumeFrom = 'initiate',
        }) {
            const fileLabel = getFileLabel(
                file,
                index,
                activeFiles.length,
            );

            if (resumeFrom === 'initiate') {
                setStatus(`Подготавливаем ${fileLabel}.`);
                setQueueItemStatus(
                    queueItem,
                    `${fileLabel} — подготовка…`,
                    'progress',
                );

                try {
                    uploadData = await initiateUpload(file);
                } catch (error) {
                    throw new UploadFlowError({
                        cause: error,
                        stage: 'initiate',
                    });
                }
            }

            if (resumeFrom !== 'complete') {
                setStatus(`Передаём ${fileLabel} в хранилище.`);
                setQueueItemStatus(
                    queueItem,
                    `${fileLabel} — передача файла…`,
                    'progress',
                );

                try {
                    await runWithRetry(
                        () => uploadFile(
                            file,
                            uploadData.upload.transport,
                        ),
                        STORAGE_RETRY_DELAYS,
                        (delay) => {
                            setStatus(
                                `${fileLabel}: повторяем передачу `
                                + `через ${delay / 1000} с…`,
                            );
                        },
                    );
                } catch (error) {
                    throw new UploadFlowError({
                        cause: error,
                        stage: 'upload',
                        uploadData,
                    });
                }
            }

            setStatus(`Подтверждаем ${fileLabel}.`);
            setQueueItemStatus(
                queueItem,
                `${fileLabel} — подтверждение…`,
                'progress',
            );

            try {
                await runWithRetry(
                    () => completeUpload(
                        uploadData.upload.complete_url,
                    ),
                    COMPLETE_RETRY_DELAYS,
                    (delay) => {
                        setStatus(
                            `${fileLabel}: повторяем подтверждение `
                            + `через ${delay / 1000} с…`,
                        );
                    },
                );
            } catch (error) {
                throw new UploadFlowError({
                    cause: error,
                    stage: 'complete',
                    uploadData,
                });
            }

            setQueueItemStatus(
                queueItem,
                `${fileLabel} — загружен`,
                'success',
            );
        }

        async function runQueue(
            startIndex = 0,
            resumeContext = null,
        ) {
            setLoading(true);
            showRetryButton(false);

            for (
                let index = startIndex;
                index < activeFiles.length;
                index += 1
            ) {
                const file = activeFiles[index];
                const queueItem = queueItems[index];

                const isResumedFile = (
                    resumeContext
                    && index === resumeContext.index
                );

                try {
                    await processFile({
                        file,
                        index,
                        queueItem,
                        uploadData: isResumedFile
                            ? resumeContext.uploadData
                            : null,
                        resumeFrom: isResumedFile
                            ? resumeContext.stage
                            : 'initiate',
                    });
                } catch (error) {
                    failedContext = {
                        file,
                        index,
                        queueItem,
                        uploadData: error.uploadData,
                        stage: error.stage,
                    };

                    const fileLabel = getFileLabel(
                        file,
                        index,
                        activeFiles.length,
                    );

                    setQueueItemStatus(
                        queueItem,
                        `${fileLabel} — ошибка: ${error.message}`,
                        'error',
                    );

                    if (error.uploadData) {
                        setStatus(
                            'Загрузка остановлена. '
                            + 'Можно повторить текущий файл.',
                            true,
                        );
                        showRetryButton(true);
                    } else {
                        setStatus(
                            'Не удалось начать загрузку. '
                            + 'Обновите страницу и попробуйте снова.',
                            true,
                        );
                    }

                    setLoading(false);
                    return;
                }

                resumeContext = null;
            }

            setStatus('Все треки загружены. Обновляем страницу…');
            input.value = '';

            window.location.reload();
        }

        submitButton.addEventListener('click', async () => {
            const files = Array.from(input.files);

            if (!files.length) {
                setStatus(
                    'Выберите хотя бы один аудиофайл для загрузки.',
                    true,
                );
                return;
            }

            activeFiles = files;
            queueItems = createQueue(files);
            failedContext = null;

            setStatus(`Выбрано файлов: ${files.length}.`);

            await runQueue();
        });

        retryButton?.addEventListener('click', async () => {
            if (!failedContext) {
                return;
            }

            await runQueue(
                failedContext.index,
                failedContext,
            );
        });
    });
}());
