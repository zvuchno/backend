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

        submitButton.addEventListener('click', async () => {
            const file = input.files[0];

            if (!file) {
                setStatus(
                    'Выберите аудиофайл для загрузки.',
                    true,
                );
                return;
            }

            setLoading(true);
            setStatus('Подготавливаем загрузку…');

            try {
                const initiateData = await initiateUpload(file);

                setStatus('Передаём файл в хранилище…');

                await uploadFile(
                    file,
                    initiateData.upload.transport,
                );

                setStatus('Подтверждаем загрузку…');

                await completeUpload(
                    initiateData.upload.complete_url,
                );

                setStatus('Трек загружен. Обновляем страницу…');

                window.location.reload();
            } catch (error) {
                setStatus(
                    error.message || 'Не удалось загрузить трек.',
                    true,
                );
                setLoading(false);
            }
        });
    });
}());
