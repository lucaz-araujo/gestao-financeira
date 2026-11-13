$(function () {

  /* Functions */

  var loadForm = function () {
    $.ajax({
      url: $(this).data("form"),
      type: 'get',
      dataType: 'json',
      success: function (data) {
        $("#editModal .modal-content").html(data.html_form);
      }
    });
  };

  var saveForm = function () {
    var form = $(this);
    $.ajax({
      url: form.attr("action"),
      data: form.serialize(),
      type: form.attr("method"),
      dataType: 'json',
      success: function (data) {
        if (data.form_is_valid) {
          $("#dataTables-example tbody").html(data.html_produtos_list);
          $("#editModal").modal("hide");
        }
        else {
          $("#editModal .modal-content").html(data.html_form);
        }
      }
    });
    return false;
  };


  /* Binding */

  // Create book
  $(".js-create-produto").click(loadForm);
  $("#editModal").on("submit", ".js-produto-create-form", saveForm);

  // Update book
  $("#dataTables-example").on("click", ".js-update-produto", loadForm);
  $("#editModal").on("submit", ".js-produto-update-form", saveForm);

});