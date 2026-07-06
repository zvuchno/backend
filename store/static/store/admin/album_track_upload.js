(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const root = document.querySelector('[data-track-upload]');

        if (!root) {
            return;
        }

        const input = root.querySelector('#id_track_upload_file');
        const submitButton = root.querySelector(
            '[data-track-upload-submit]',
        );
        const statusElement = root.querySelector(
            '[data-track-upload-status]',
        );
        const uploadList = root.querySelector(
            '[data-track-upload-list]',
        );
        const initiateUrl = root.dataset.initiateUrl;

        function setStatus(message, isError = false) {
            statusElement.textContent = message;
            statusElement.classList.toggle('errornote', isError);
        }

        function setLoading(isLoading) {
            submitButton.disabled = isLoading;
            input.disabled = isLoading;
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

        function setQueueItemStatus(item, message, isError = false) {
            item.textContent = message;
            item.classList.toggle('error', isError);
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
            const response = await fetch(initiateUrl, {
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

            if (!response.ok) {
                throw new Error(
                    await getErrorMessage(
                        response,
                        'Не удалось подготовить загрузку трека.',
                    ),
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

            const response = await fetch(transport.url, {
                method: transport.method,
                credentials: 'same-origin',
                headers: transport.headers,
                body: formData,
            });

            if (!response.ok) {
                throw new Error(
                    await getErrorMessage(
                        response,
                        'Не удалось передать файл в хранилище.',
                    ),
                );
            }
        }

        async function completeUpload(completeUrl) {
            const response = await fetch(completeUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                },
            });

            if (!response.ok) {
                throw new Error(
                    await getErrorMessage(
                        response,
                        'Не удалось завершить загрузку трека.',
                    ),
                );
            }

            return response.json();
        }

        async function uploadSingleFile(file) {
            const initiateData = await initiateUpload(file);

            await uploadFile(
                file,
                initiateData.upload.transport,
            );

            await completeUpload(
                initiateData.upload.complete_url,
            );
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

            const queueItems = createQueue(files);

            setLoading(true);
            setStatus(`Выбрано файлов: ${files.length}.`);

            try {
                for (const [index, file] of files.entries()) {
                    const queueItem = queueItems[index];
                    const fileLabel = getFileLabel(
                        file,
                        index,
                        files.length,
                    );

                    setStatus(`Загружается ${fileLabel}.`);
                    setQueueItemStatus(
                        queueItem,
                        `${fileLabel} — загрузка…`,
                    );

                    await uploadSingleFile(file);

                    setQueueItemStatus(
                        queueItem,
                        `${fileLabel} — загружен`,
                    );
                }

                setStatus('Все треки загружены. Обновляем страницу…');
                input.value = '';

                window.location.reload();
            } catch (error) {
                const currentItem = queueItems.find(
                    (item) => item.textContent.endsWith('— загрузка…'),
                );

                if (currentItem) {
                    setQueueItemStatus(
                        currentItem,
                        `${currentItem.textContent.replace(
                            '— загрузка…',
                            '— ошибка',
                        )}: ${
                            error.message
                            || 'Не удалось загрузить файл.'
                        }`,
                        true,
                    );
                }

                setStatus(
                    'Загрузка остановлена. Уже загруженные треки сохранены.',
                    true,
                );
                setLoading(false);
            }
        });
    });
}());
