def remove_content_from_no_content_responses(
    result,
    generator,
    request,
    public,
):
    """Удаляет content из ответов 204 No Content."""
    for path_item in result.get('paths', {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue

            responses = operation.get('responses')
            if not responses:
                continue

            response = responses.get('204')
            if response:
                response.pop('content', None)

    return result
